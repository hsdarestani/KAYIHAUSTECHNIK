from erp.models import UserProfile

ROLE_RANK = {
    UserProfile.Role.READONLY: 0,
    UserProfile.Role.TECHNICIAN: 1,
    UserProfile.Role.OFFICE: 2,
    UserProfile.Role.ACCOUNTING: 2,
    UserProfile.Role.PROJECT_MANAGER: 3,
    UserProfile.Role.ADMIN: 4,
}


def role_for(user):
    if user.is_superuser:
        return UserProfile.Role.ADMIN
    profile = getattr(user, "profile", None)
    return profile.role if profile else UserProfile.Role.READONLY


def can_write(user) -> bool:
    return ROLE_RANK.get(role_for(user), 0) >= 1 and role_for(user) != UserProfile.Role.READONLY


def can_manage_finance(user) -> bool:
    return user.is_superuser or role_for(user) in {
        UserProfile.Role.ADMIN,
        UserProfile.Role.ACCOUNTING,
        UserProfile.Role.PROJECT_MANAGER,
    }


def can_approve_automation(user) -> bool:
    return user.is_superuser or ROLE_RANK.get(role_for(user), 0) >= 3


def can_view_prices(user) -> bool:
    if user.is_superuser:
        return True
    role = role_for(user)
    if role in {UserProfile.Role.ADMIN, UserProfile.Role.OFFICE, UserProfile.Role.PROJECT_MANAGER, UserProfile.Role.ACCOUNTING}:
        return True
    employee = getattr(user, "employee", None)
    return bool(employee and employee.can_view_prices)
