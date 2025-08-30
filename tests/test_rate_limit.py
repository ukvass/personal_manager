def test_login_rate_limit(client):
    # Register a user first
    r = client.post("/auth/register", json={"email": "rl@example.com", "password": "secret"})
    assert r.status_code in (200, 201)

    # Hit login with wrong password 5 times (allowed)
    for i in range(5):
        r_bad = client.post(
            "/auth/login",
            data={"username": "rl@example.com", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r_bad.status_code == 401

    # 6th attempt within the same minute should be rate limited
    r_limit = client.post(
        "/auth/login",
        data={"username": "rl@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r_limit.status_code == 429


def test_register_rate_limit(client):
    # First three registrations should pass
    for i in range(3):
        r = client.post(
            "/auth/register",
            json={"email": f"rate{i}@example.com", "password": "x"},
        )
        assert r.status_code in (200, 201)

    # Fourth within the same minute should hit the limiter
    r4 = client.post(
        "/auth/register",
        json={"email": "rate3@example.com", "password": "x"},
    )
    assert r4.status_code == 429

