/**
 * check_contract.mjs
 * Validates frontend/src/api/*.js calls against the live backend openapi.json.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import * as acorn from 'acorn';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const API_DIR = path.resolve(__dirname, '../src/api');
const OPENAPI_URL = process.env.OPENAPI_URL || 'http://localhost:8000/openapi.json';

// Normalize path templates: convert ${var} or {var} to {param} for flexible matching
function normalizePath(p) {
  return p
    .replace(/\$\{[^}]+\}/g, '{param}')
    .replace(/\{[^}]+\}/g, '{param}')
    .replace(/\/+/g, '/');
}

// Convert template literal to OpenAPI-style path template: `/users/${userId}/active` -> `/users/{userId}/active`
function templateLiteralToPath(node) {
  let result = '';
  for (let i = 0; i < node.quasis.length; i++) {
    result += node.quasis[i].value.raw;
    if (i < node.expressions.length) {
      const expr = node.expressions[i];
      const paramName = expr.name || `param${i}`;
      result += `{${paramName}}`;
    }
  }
  return result;
}

// Extract body fields from AST nodes
function extractBodyFields(bodyNode, enclosingFunction) {
  if (!bodyNode) return [];

  // Case 1: Inline ObjectExpression: { a: 1, b: 2 }
  if (bodyNode.type === 'ObjectExpression') {
    return bodyNode.properties
      .filter((p) => p.type === 'Property')
      .map((p) => p.key.name || p.key.value)
      .filter(Boolean);
  }

  // Case 2: Identifier (e.g. payload, data, formData)
  if (bodyNode.type === 'Identifier') {
    const varName = bodyNode.name;
    const fields = new Set();

    // Scan enclosing function body for assignments to this identifier
    if (enclosingFunction) {
      traverse(enclosingFunction, (n) => {
        // payload.field = ...
        if (
          n.type === 'AssignmentExpression' &&
          n.left.type === 'MemberExpression' &&
          n.left.object.type === 'Identifier' &&
          n.left.object.name === varName
        ) {
          const field = n.left.property.name || n.left.property.value;
          if (field) fields.add(field);
        }

        // const payload = { a: 1, b: 2 }
        if (
          n.type === 'VariableDeclarator' &&
          n.id.type === 'Identifier' &&
          n.id.name === varName &&
          n.init &&
          n.init.type === 'ObjectExpression'
        ) {
          for (const p of n.init.properties) {
            if (p.type === 'Property') {
              const field = p.key.name || p.key.value;
              if (field) fields.add(field);
            }
          }
        }

        // formData.append('fieldName', ...)
        if (
          n.type === 'CallExpression' &&
          n.callee.type === 'MemberExpression' &&
          n.callee.object.type === 'Identifier' &&
          n.callee.object.name === varName &&
          n.callee.property.name === 'append' &&
          n.arguments.length > 0 &&
          n.arguments[0].type === 'Literal'
        ) {
          fields.add(String(n.arguments[0].value));
        }
      });
    }

    return Array.from(fields);
  }

  return [];
}

// Simple AST Traversal
function traverse(node, visitor) {
  if (!node || typeof node !== 'object') return;
  visitor(node);
  for (const key of Object.keys(node)) {
    if (key === 'parent') continue;
    const child = node[key];
    if (Array.isArray(child)) {
      for (const c of child) traverse(c, visitor);
    } else if (child && typeof child === 'object') {
      traverse(child, visitor);
    }
  }
}

// Parse frontend API files
function extractFrontendCalls() {
  const calls = [];
  const files = fs.readdirSync(API_DIR).filter((f) => f.endsWith('.js'));

  for (const file of files) {
    const filePath = path.join(API_DIR, file);
    const code = fs.readFileSync(filePath, 'utf8');
    const ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'module' });

    let currentFunction = null;

    traverse(ast, (node) => {
      if (
        node.type === 'FunctionDeclaration' ||
        node.type === 'FunctionExpression' ||
        node.type === 'ArrowFunctionExpression' ||
        node.type === 'MethodDefinition' ||
        (node.type === 'Property' && (node.value.type === 'FunctionExpression' || node.value.type === 'ArrowFunctionExpression'))
      ) {
        currentFunction = node;
      }

      if (
        node.type === 'CallExpression' &&
        node.callee.type === 'MemberExpression' &&
        node.callee.object.type === 'Identifier' &&
        node.callee.object.name === 'api'
      ) {
        const method = (node.callee.property.name || '').toUpperCase();
        if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) return;

        const pathArg = node.arguments[0];
        let rawPath = '';
        if (pathArg.type === 'Literal') {
          rawPath = String(pathArg.value);
        } else if (pathArg.type === 'TemplateLiteral') {
          rawPath = templateLiteralToPath(pathArg);
        }

        const bodyArg = ['POST', 'PUT', 'PATCH'].includes(method) ? node.arguments[1] : null;
        let bodyFields = [];
        if (bodyArg) {
          // Check if bodyArg is options object like { params } or { headers }
          const isOptionsOnly =
            bodyArg.type === 'ObjectExpression' &&
            bodyArg.properties.every(
              (p) => p.type === 'Property' && ['params', 'headers', 'responseType'].includes(p.key.name)
            );
          if (!isOptionsOnly) {
            bodyFields = extractBodyFields(bodyArg, currentFunction);
          }
        }

        calls.push({
          file,
          method,
          path: rawPath,
          normalizedPath: normalizePath(rawPath),
          bodyFields,
        });
      }
    });
  }

  return calls;
}

// Fetch OpenAPI schema from live backend (or fallback to local openapi.json)
async function fetchOpenApi() {
  try {
    const res = await fetch(OPENAPI_URL);
    if (!res.ok) {
      throw new Error(`Failed to fetch OpenAPI schema: HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    const localFallback = path.resolve(__dirname, '../openapi.json');
    if (fs.existsSync(localFallback)) {
      console.warn(`\x1b[33mWarning: Could not connect to ${OPENAPI_URL} (${err.message}). Using local snapshot ${localFallback}\x1b[0m\n`);
      return JSON.parse(fs.readFileSync(localFallback, 'utf8'));
    }
    console.error(`\x1b[31mError connecting to ${OPENAPI_URL}: ${err.message}\x1b[0m`);
    process.exit(1);
  }
}

// Resolve OpenAPI schema properties & required fields
function resolveSchema(schemaRef, openapi) {
  if (!schemaRef) return { properties: [], required: [] };

  let target = schemaRef;
  if (target.$ref) {
    const sname = target.$ref.split('/').pop();
    target = openapi.components?.schemas?.[sname] || {};
  }

  // Handle allOf/anyOf/oneOf
  const properties = new Set(Object.keys(target.properties || {}));
  const required = new Set(target.required || []);

  if (target.allOf) {
    for (const sub of target.allOf) {
      const subRes = resolveSchema(sub, openapi);
      subRes.properties.forEach((p) => properties.add(p));
      subRes.required.forEach((r) => required.add(r));
    }
  }

  return {
    properties: Array.from(properties),
    required: Array.from(required),
  };
}

// Run Contract Diff
async function main() {
  console.log('\n======================================================');
  console.log('   SVSU No-Dues — Frontend vs Backend Contract Check   ');
  console.log('======================================================\n');
  console.log(`Connecting to backend at: ${OPENAPI_URL}`);

  const openapi = await fetchOpenApi();
  const frontendCalls = extractFrontendCalls();
  const openapiPaths = openapi.paths || {};

  console.log(`Loaded ${frontendCalls.length} frontend API calls across src/api/*.js`);
  console.log(`Loaded ${Object.keys(openapiPaths).length} paths from live backend OpenAPI contract.\n`);

  // Build map of normalized backend endpoints
  const backendEndpoints = [];
  for (const [p, methods] of Object.entries(openapiPaths)) {
    for (const [m, op] of Object.entries(methods)) {
      if (['get', 'post', 'put', 'patch', 'delete'].includes(m.toLowerCase())) {
        const methodUpper = m.toUpperCase();
        const requestBody = op.requestBody;
        let schemaProps = [];
        let schemaRequired = [];

        if (requestBody && requestBody.content) {
          const jsonContent =
            requestBody.content['application/json'] ||
            requestBody.content['application/x-www-form-urlencoded'] ||
            requestBody.content['multipart/form-data'];
          if (jsonContent?.schema) {
            const resolved = resolveSchema(jsonContent.schema, openapi);
            schemaProps = resolved.properties;
            schemaRequired = resolved.required;
          }
        }

        backendEndpoints.push({
          method: methodUpper,
          path: p,
          normalizedPath: normalizePath(p),
          properties: schemaProps,
          required: schemaRequired,
        });
      }
    }
  }

  const missingCalls = [];
  const unacceptedBodyFields = [];
  const missingRequiredFields = [];
  const matchedCalls = [];

  for (const call of frontendCalls) {
    // Find matching backend endpoint by method and normalized path
    const match = backendEndpoints.find(
      (b) => b.method === call.method && b.normalizedPath === call.normalizedPath
    );

    if (!match) {
      missingCalls.push(call);
      continue;
    }

    // Check body fields
    const unaccepted = [];
    const missingReq = [];

    if (['POST', 'PUT', 'PATCH'].includes(call.method)) {
      // Body fields the backend does not accept
      if (match.properties.length > 0 && call.bodyFields.length > 0) {
        for (const f of call.bodyFields) {
          // Ignore multipart file or wildcard
          if (f === 'file' || f === 'formData') continue;
          if (!match.properties.includes(f)) {
            unaccepted.push(f);
          }
        }
      }

      // Required fields the frontend never sends
      if (match.required.length > 0 && call.bodyFields.length > 0) {
        for (const req of match.required) {
          if (!call.bodyFields.includes(req)) {
            missingReq.push(req);
          }
        }
      }
    }

    if (unaccepted.length > 0) {
      unacceptedBodyFields.push({ call, backendPath: match.path, unaccepted });
    }
    if (missingReq.length > 0) {
      missingRequiredFields.push({ call, backendPath: match.path, missingReq });
    }

    matchedCalls.push({ call, match });
  }

  // PRINT REAL REPORT OUTPUT
  console.log('--- CONTRACT VERIFICATION REPORT ---');
  console.log(`Total Frontend API Calls:     ${frontendCalls.length}`);
  console.log(`Matched Endpoints:            ${matchedCalls.length}`);
  console.log(`Unmatched Calls (404/Missing): ${missingCalls.length}`);
  console.log(`Unaccepted Body Fields:       ${unacceptedBodyFields.length}`);
  console.log(`Missing Required Fields:      ${missingRequiredFields.length}`);
  console.log('------------------------------------\n');

  let hasError = false;

  // 1. Calls whose method+path do not exist
  if (missingCalls.length > 0) {
    hasError = true;
    console.log('\x1b[31m[!] CALLS WHOSE METHOD+PATH DO NOT EXIST IN BACKEND:\x1b[0m');
    for (const item of missingCalls) {
      console.log(`  - \x1b[33m${item.file}\x1b[0m: ${item.method} ${item.path}`);
    }
    console.log('');
  } else {
    console.log('\x1b[32m[✓] All frontend calls have matching backend method+path routes.\x1b[0m\n');
  }

  // 2. Body fields backend does not accept
  if (unacceptedBodyFields.length > 0) {
    hasError = true;
    console.log('\x1b[31m[!] BODY FIELDS THE BACKEND DOES NOT ACCEPT:\x1b[0m');
    for (const item of unacceptedBodyFields) {
      console.log(
        `  - \x1b[33m${item.call.file}\x1b[0m: ${item.call.method} ${item.backendPath}\n` +
        `    Unaccepted fields: \x1b[31m${item.unaccepted.join(', ')}\x1b[0m`
      );
    }
    console.log('');
  } else {
    console.log('\x1b[32m[✓] No extraneous or unaccepted body fields found.\x1b[0m\n');
  }

  // 3. Required backend fields frontend never sends
  if (missingRequiredFields.length > 0) {
    hasError = true;
    console.log('\x1b[31m[!] REQUIRED BACKEND FIELDS FRONTEND NEVER SENDS:\x1b[0m');
    for (const item of missingRequiredFields) {
      console.log(
        `  - \x1b[33m${item.call.file}\x1b[0m: ${item.call.method} ${item.backendPath}\n` +
        `    Missing required fields: \x1b[31m${item.missingReq.join(', ')}\x1b[0m`
      );
    }
    console.log('');
  } else {
    console.log('\x1b[32m[✓] All required backend fields are sent by frontend calls.\x1b[0m\n');
  }

  // 4. Verification table of verified endpoints
  console.log('--- VERIFIED ENDPOINT CALLS ---');
  for (const { call, match } of matchedCalls) {
    const fieldsStr = call.bodyFields.length > 0 ? ` [body: ${call.bodyFields.join(', ')}]` : '';
    console.log(`  ✓ [${call.method}] ${match.path}${fieldsStr} (${call.file})`);
  }
  console.log('-------------------------------\n');

  if (hasError) {
    console.log('\x1b[31mCONTRACT CHECK RESULT: FAILED (mismatches detected)\x1b[0m');
    process.exit(1);
  } else {
    console.log('\x1b[32mCONTRACT CHECK RESULT: PASSED (100% contract compliance)\x1b[0m');
    process.exit(0);
  }
}

main();
