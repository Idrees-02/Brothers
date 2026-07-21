from app.domain.permissions import Permission, user_has_permission


def make_user(**overrides):
    base = {
        "is_admin": 0,
        "can_create_invoice": 0,
        "can_edit_invoice": 0,
        "can_view_only": 0,
        "can_create_voucher": 0,
        "can_register_attendance": 0,
    }
    base.update(overrides)
    return base


def test_admin_bypasses_everything():
    admin = make_user(is_admin=1)
    for perm in Permission:
        assert user_has_permission(admin, perm)


def test_flag_grants_specific_permission():
    user = make_user(can_create_invoice=1)
    assert user_has_permission(user, Permission.CREATE_INVOICE)
    assert not user_has_permission(user, Permission.EDIT_INVOICE)


def test_view_only_vetoes_write_actions_even_if_also_set():
    user = make_user(can_view_only=1, can_create_invoice=1, can_edit_invoice=1, can_create_voucher=1)
    assert not user_has_permission(user, Permission.CREATE_INVOICE)
    assert not user_has_permission(user, Permission.EDIT_INVOICE)
    assert not user_has_permission(user, Permission.CREATE_VOUCHER)


def test_view_only_does_not_veto_attendance():
    user = make_user(can_view_only=1, can_register_attendance=1)
    assert user_has_permission(user, Permission.REGISTER_ATTENDANCE)


def test_no_permission_by_default():
    user = make_user()
    for perm in Permission:
        if perm is Permission.VIEW_ONLY:
            continue
        assert not user_has_permission(user, perm)
