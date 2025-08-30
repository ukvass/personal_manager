def test_register_web_success(client):
    # Fetch registration form to get CSRF token
    r_form = client.get("/register")
    assert r_form.status_code == 200
    csrftoken = r_form.cookies.get("csrftoken")
    assert csrftoken

    # Submit registration
    email = "ui_reg@example.com"
    r_post = client.post(
        "/register",
        data={
            "email": email,
            "password": "secret-123",
            "csrf_token": csrftoken,
        },
        follow_redirects=False,
    )
    # UI flow redirects to home after success and sets access_token cookie
    assert r_post.status_code in (302, 303)
    assert r_post.cookies.get("access_token")


def test_register_web_duplicate_email(client):
    # First, register a user
    r_form = client.get("/register")
    token = r_form.cookies.get("csrftoken")
    assert token
    email = "dup@example.com"
    r_ok = client.post(
        "/register",
        data={"email": email, "password": "x", "csrf_token": token},
        follow_redirects=False,
    )
    assert r_ok.status_code in (302, 303)

    # Try to register the same email again — expect 400 with error page
    r_form2 = client.get("/register")
    token2 = r_form2.cookies.get("csrftoken")
    assert token2
    r_dup = client.post(
        "/register",
        data={"email": email, "password": "x", "csrf_token": token2},
        follow_redirects=False,
    )
    assert r_dup.status_code == 400
