"""Import all models so Alembic autogenerate sees them."""
from backend.app.models.university import Faculty, Department, Programme  # noqa: F401
from backend.app.models.lab_course import LabCourse  # noqa: F401
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment  # noqa: F401
from backend.app.models.user import User  # noqa: F401
from backend.app.models.bank import BankDetail  # noqa: F401
from backend.app.models.clearance import ClearanceRequest, DepartmentApproval  # noqa: F401
from backend.app.models.certificate import Certificate  # noqa: F401
from backend.app.models.refund import Refund  # noqa: F401
from backend.app.models.audit import AuditLog  # noqa: F401
from backend.app.models.otp import SignupOTP  # noqa: F401
from backend.app.models.email import EmailOutbox  # noqa: F401
from backend.app.models.rate_limit import AuthRateLimit  # noqa: F401
