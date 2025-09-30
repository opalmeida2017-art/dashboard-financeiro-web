# models.py
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, email, nome, apartamento_id, role):
        self.id = id
        self.email = email
        self.nome = nome
        self.apartamento_id = apartamento_id
        self.role = role