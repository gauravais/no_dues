/**
 * Shri Vishwakarma Skill University (SVSU) Department Structure
 * Referenced for Admin User Provisioning and Assigned Labs/Workshops mapping
 */

export const ACADEMIC_DEPARTMENTS = [
  { id: 4, name: 'Skill Department of CS/IT', kind: 'academic' },
  { id: 5, name: 'Skill Department of Industry 4.0', kind: 'academic' },
  { id: 1, name: 'Skill Department of Automotive Studies', kind: 'academic' },
  { id: 2, name: 'Skill Department of Construction Management and Technology', kind: 'academic' },
  { id: 3, name: 'Skill Department of Green Technology', kind: 'academic' },
  { id: 6, name: 'Skill Department of Plastic Technology', kind: 'academic' },
]

export const SERVICE_DEPARTMENTS_ALWAYS = [
  { id: 7, name: 'Library', kind: 'service' },
  { id: 8, name: 'Computer Lab/Centre', kind: 'service' },
  { id: 9, name: 'General/Transportation Branch', kind: 'service' },
  { id: 10, name: 'Dean Student Welfare', kind: 'service' },
  { id: 11, name: 'Sports', kind: 'service' },
  { id: 12, name: 'N.S.S.', kind: 'service' },
  { id: 13, name: 'R&S Branch', kind: 'service' },
  { id: 14, name: 'IIC', kind: 'service' },
  { id: 15, name: 'Account Section', kind: 'service' },
  { id: 16, name: 'Hostel (Boys/Girls)', kind: 'service' },
]

export const ASSIGNABLE_DEPARTMENTS = [
  { id: 17, name: 'Lab-1', kind: 'service' },
  { id: 18, name: 'Lab-2', kind: 'service' },
  { id: 19, name: 'Lab-3', kind: 'service' },
  { id: 20, name: 'Lab-4', kind: 'service' },
  { id: 21, name: 'Lab-5', kind: 'service' },
  { id: 22, name: 'Lab-6', kind: 'service' },
  { id: 23, name: 'Lab-7', kind: 'service' },
  { id: 24, name: 'Lab-8', kind: 'service' },
  { id: 25, name: 'Lab-9', kind: 'service' },
  { id: 26, name: 'Workshop-1', kind: 'service' },
  { id: 27, name: 'Workshop-2', kind: 'service' },
  { id: 28, name: 'Workshop-3', kind: 'service' },
  { id: 29, name: 'Others', kind: 'service' },
]

export const ALL_DEPARTMENTS = [
  ...ACADEMIC_DEPARTMENTS,
  ...SERVICE_DEPARTMENTS_ALWAYS,
  ...ASSIGNABLE_DEPARTMENTS,
]

export function getDepartmentById(id) {
  return ALL_DEPARTMENTS.find((d) => d.id === Number(id))
}
