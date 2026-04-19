from app import app, db, User

with app.app_context():

    users = [
        {"username": "employee1", "password": "emp123", "role": "employee"},
        {"username": "employee2", "password": "emp123", "role": "employee"},
        {"username": "senior1", "password": "senior123", "role": "senior"},
        {"username": "manager1", "password": "manager123", "role": "manager"},
    ]

    for u in users:
        existing = User.query.filter_by(username=u["username"]).first()
        if not existing:
            db.session.add(User(
                username=u["username"],
                password=u["password"],
                role=u["role"]
            ))

    db.session.commit()

    print("✅ Users created successfully!")
