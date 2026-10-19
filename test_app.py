
import app as expense_app


def test_flask_application_exists():
    assert expense_app.app is not None


def test_login_route_exists():
    rules = [
        rule.rule
        for rule in expense_app.app.url_map.iter_rules()
    ]

    assert "/login" in rules
