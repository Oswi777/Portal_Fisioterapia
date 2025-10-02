import bcrypt

# Cambia esta contraseña por la que quieras usar
password_plana = "admin123"
hash = bcrypt.hashpw(password_plana.encode('utf-8'), bcrypt.gensalt())

print(hash.decode())  # Copia esta cadena y pégala en el SQL
