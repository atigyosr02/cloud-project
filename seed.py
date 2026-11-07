import json
import os
import bcrypt
import psycopg2
from psycopg2.extras import execute_values


def main() -> None:
    accounts = [
        ("Administrateur Démo", "admin@medicare.test", "admin", os.environ.get("SEED_ADMIN_PASSWORD")),
        ("Dr Amira Ben Salem", "amira@medicare.test", "medecin", os.environ.get("SEED_DOCTOR1_PASSWORD")),
        ("Dr Yassine Trabelsi", "yassine@medicare.test", "medecin", os.environ.get("SEED_DOCTOR2_PASSWORD")),
        ("Sana Khelifi", "sana@medicare.test", "secretaire", os.environ.get("SEED_SECRETARY_PASSWORD")),
        ("Ines Gharbi", "patient1@exemple.test", "patient", os.environ.get("SEED_PATIENT_PASSWORD")),
    ]
    if any(
        not password
        or len(password) < 8
        or len(password.encode("utf-8")) > 72
        or not any(char.isdigit() for char in password)
        for *_, password in accounts
    ):
        raise SystemExit("Définissez les quatre mots de passe SEED_* (8 à 72 octets et un chiffre).")
    connection = psycopg2.connect(
        host=os.environ.get("DB_HOST", "postgres"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "medicare"),
        user=os.environ.get("DB_USER", "medicare"),
        password=os.environ.get("DB_PASSWORD", ""),
        sslmode=os.environ.get("DB_SSLMODE", "prefer"),
        sslrootcert=os.environ.get("DB_SSLROOTCERT") or None,
    )
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
            cursor.execute(
                "ALTER TABLE users ADD CONSTRAINT users_role_check "
                "CHECK (role IN ('admin', 'medecin', 'secretaire', 'patient'))"
            )
            cursor.execute(
                "ALTER TABLE patients ADD COLUMN IF NOT EXISTS user_id BIGINT UNIQUE "
                "REFERENCES users(id) ON DELETE SET NULL"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS prescriptions ("
                "id BIGSERIAL PRIMARY KEY, "
                "patient_id BIGINT NOT NULL REFERENCES patients(id), "
                "doctor_id BIGINT NOT NULL REFERENCES users(id), "
                "medicines TEXT NOT NULL CHECK (char_length(medicines) BETWEEN 1 AND 10000), "
                "instructions VARCHAR(3000), "
                "prescribed_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_prescriptions_patient_date "
                "ON prescriptions (patient_id, prescribed_at DESC)"
            )
            cursor.execute(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS label VARCHAR(120) "
                "NOT NULL DEFAULT 'Document médical'"
            )
            for name, email, role, password in accounts:
                hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cursor.execute(
                    "INSERT INTO users (name, email, role, password_hash) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (email) DO NOTHING",
                    (name, email, role, hashed),
                )
            names = [
                ("Ines", "Gharbi"), ("Sami", "Masmoudi"), ("Meriem", "Jaziri"), ("Fares", "Bouzid"),
                ("Nour", "Chaabane"), ("Anis", "Mejri"), ("Rania", "Haddad"), ("Tarek", "Ben Amor"),
                ("Yasmine", "Kammoun"), ("Malek", "Saidi"), ("Dorra", "Ayari"), ("Khalil", "Mhenni"),
                ("Lina", "Abid"), ("Bilel", "Jebali"), ("Salma", "Karray"), ("Omar", "Dridi"),
                ("Alaa", "Baccouche"), ("Hiba", "Zouari"), ("Seif", "Mokni"), ("Rim", "Ferchichi"),
            ]
            patients = [
                (f"{first} {last}", f"+216 20 {410000 + index}", f"patient{index + 1}@exemple.test")
                for index, (first, last) in enumerate(names)
            ]
            execute_values(
                cursor,
                "INSERT INTO patients (full_name, phone, email) VALUES %s "
                "ON CONFLICT DO NOTHING",
                patients,
            )
            cursor.execute(
                "UPDATE patients SET user_id = users.id FROM users "
                "WHERE patients.email = users.email AND users.role = 'patient' AND users.email = %s",
                ("patient1@exemple.test",),
            )
    finally:
        connection.close()
    print(json.dumps({"level": "INFO", "message": "Données fictives initialisées."}, ensure_ascii=False))


if __name__ == "__main__":
    main()