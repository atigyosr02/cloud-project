# MediCare Cabinet

Application de démonstration en français pour la gestion d’un cabinet médical. Tous les noms, coordonnées et dossiers fournis par `seed.py` sont fictifs. Ne saisissez pas de vraies données de santé dans cette démonstration.

## Lancement local

Prérequis : Docker Engine avec le plugin Compose.

1. Copier `.env.example` vers `.env` et remplacer les valeurs `replace_*` restantes par des valeurs locales. Les mots de passe de démonstration listés ci-dessous sont réservés aux essais locaux. La clé `SECRET_KEY` doit être longue et aléatoire.
2. À la racine du projet, lancer `docker compose up --build`.
3. Ouvrir `http://localhost:5000`. La base PostgreSQL initialise `schema.sql`; le conteneur applicatif exécute ensuite `seed.py` avant Gunicorn. Les documents MinIO restent dans le volume Docker, jamais sur le disque applicatif.

La console MinIO locale est disponible sur `http://localhost:9001` avec les identifiants `S3_ACCESS_KEY` et `S3_SECRET_KEY` de `.env`. Le bucket est créé à la première opération document.

Compose utilise l’image MinIO compatible S3 `bitnamilegacy/minio` pour le développement local; la configuration AWS remplace entièrement MinIO par S3.

Pour arrêter les conteneurs : `docker compose down`. Pour supprimer aussi les données locales de démonstration : `docker compose down -v` (cette commande efface les volumes PostgreSQL et MinIO).

## Comptes de démonstration

Les comptes ci-dessous sont créés par `seed.py`. Ces mots de passe de démonstration sont publics et réservés aux essais locaux; ne les utilisez jamais en production ni avec des données réelles.

| Rôle | Adresse de connexion | Mot de passe local |
| --- | --- | --- |
| Administrateur | `admin@medicare.test` | `AdminDemo123!` |
| Médecin (Amira Ben Salem) | `amira@medicare.test` | `AmiraDemo123!` |
| Médecin (Yassine Trabelsi) | `yassine@medicare.test` | `YassineDemo123!` |
| Secrétariat (Sana Khelifi) | `sana@medicare.test` | `Secretariat123!` |
| Patiente fictive (Ines Gharbi) | `patient1@exemple.test` | `PatienteDemo123!` |

Les valeurs `SEED_*_PASSWORD` de `.env.example` correspondent à ces identifiants de test. `seed.py` n’écrase pas les comptes existants lors d’une relance; pour réinitialiser une base de démonstration locale, arrêtez les conteneurs et supprimez les volumes avec `docker compose down -v`, puis relancez `docker compose up --build`.

## Variables d’environnement

| Variable | Usage |
| --- | --- |
| `SECRET_KEY` | Clé secrète Flask obligatoire, à conserver dans un gestionnaire de secrets. |
| `DEBUG` | Active le mode debug uniquement si `true`; désactivé par défaut. |
| `SESSION_COOKIE_SECURE` | `true` derrière HTTPS; `false` uniquement pour le HTTP local. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Connexion PostgreSQL. |
| `DB_SSLMODE` | Mode TLS psycopg2; utiliser `verify-full` sur RDS avec le certificat CA configuré. |
| `DB_SSLROOTCERT` | Chemin vers le certificat CA RDS dans le conteneur, si `verify-full` est utilisé. |
| `S3_BUCKET` | Bucket privé de documents. |
| `S3_ENDPOINT_URL` | Endpoint MinIO local; laisser vide sur AWS pour utiliser l’endpoint régional S3. |
| `S3_PUBLIC_ENDPOINT_URL` | Endpoint employé uniquement pour les URL pré-signées vues par le navigateur; Compose le règle à `http://localhost:9000`, laisser vide sur AWS. |
| `AWS_REGION` | Région du bucket S3, par exemple `eu-west-3`. |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Identifiants MinIO locaux seulement. Ne pas définir de clés S3 sur AWS : boto3 utilisera le rôle IAM de l’instance. |
| `SEED_ADMIN_PASSWORD`, `SEED_DOCTOR1_PASSWORD`, `SEED_DOCTOR2_PASSWORD`, `SEED_SECRETARY_PASSWORD`, `SEED_PATIENT_PASSWORD` | Mots de passe initiaux fournis à `seed.py`, jamais conservés en clair en base. Les valeurs d’exemple sont réservées aux essais locaux. |
| `RATELIMIT_STORAGE_URI` | Stockage Flask-Limiter; `memory://` en local, Redis/ElastiCache partagé en production multi-processus. |
| `APP_PORT` | Port HTTP local publié par Compose, `5000` par défaut. |

## Rôles et protection des données

- `admin` : gestion et désactivation des comptes, consultation du journal d’activité.
- `medecin` : consultation des dossiers, notes médicales et documents privés.
- `secretaire` : informations administratives des patients et rendez-vous; les routes médicales et de documents répondent 403 côté serveur.
- `patient` : accès à son propre dossier, à ses consultations, ordonnances et documents via un lien vérifié avec son compte, ainsi qu’à ses prochains rendez-vous; aucun accès aux dossiers d’autres patients ni aux fonctions du cabinet.
- À l’enregistrement d’une ordonnance, un PDF est généré sans fichier temporaire local, stocké dans S3/MinIO et ajouté à la rubrique « Documents médicaux » avec le libellé « Ordonnance médicale ».
- Les formulaires POST utilisent CSRF; les mots de passe sont hachés avec bcrypt; les recherches SQL utilisent des paramètres psycopg2.
- Les téléchargements passent par une URL S3 pré-signée valable 60 secondes. Les uploads sont limités à 5 Mo et aux signatures PDF, PNG et JPEG. Les objets ont une clé UUID.
- `GET /health` vérifie la connexion PostgreSQL et renvoie `{"status":"ok"}` avec HTTP 200 quand la base répond.

## Déploiement sur AWS

Ce dépôt fournit une base de déploiement, pas une certification réglementaire ni une validation de sécurité pour des dossiers de santé réels. Avant tout usage réel, faire auditer l’application, les procédures, la conservation et la conformité applicable; ajouter sauvegardes testées, supervision, gestion du consentement, rétention/purge, rotation des secrets et contrôles d’accès opérationnels.

1. **PostgreSQL vers RDS** : créer une instance PostgreSQL privée, appliquer `schema.sql`, limiter son groupe de sécurité aux instances EC2, activer le chiffrement et les sauvegardes. Remplacer `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` et `DB_PASSWORD` par les valeurs stockées dans AWS Secrets Manager. Configurer `DB_SSLMODE=verify-full` et monter le CA RDS pour `DB_SSLROOTCERT`.
2. **MinIO vers S3** : créer un bucket S3 privé, activer le chiffrement au repos et le blocage d’accès public. Définir `S3_BUCKET` et `AWS_REGION`, laisser `S3_ENDPOINT_URL` vide et ne fournir aucune clé d’accès. Attacher au rôle IAM de l’EC2 une politique limitée à ce bucket (`s3:PutObject`, `s3:GetObject`, et les droits de lecture du bucket nécessaires). Le client boto3 utilisera automatiquement les identifiants temporaires du rôle.
3. **Secrets et cookies** : injecter `SECRET_KEY`, identifiants RDS et mots de passe de bootstrap depuis Secrets Manager au démarrage EC2; activer `SESSION_COOKIE_SECURE=true` derrière HTTPS. Ne pas copier `.env` dans l’image ni dans le dépôt.
4. **Réseau et proxy** : placer l’EC2 derrière un ALB, TLS au niveau ALB, puis CloudFront si nécessaire. `ProxyFix` ne fait confiance qu’à un saut `X-Forwarded-For`, `X-Forwarded-Proto` et `X-Forwarded-Host`; conserver une chaîne de proxy cohérente et ne pas exposer Gunicorn directement à Internet. La route `/health` est prévue pour le contrôle ALB.
5. **Limitation de débit** : en local, Gunicorn utilise un worker et le limiteur mémoire est suffisant pour la démonstration. Sur AWS avec plusieurs workers ou instances, remplacer `RATELIMIT_STORAGE_URI=memory://` par l’URI d’un Redis privé (par exemple ElastiCache), afin que la limite de connexion soit partagée.
6. **Données initiales** : provisionner le schéma et les premiers comptes via un processus contrôlé; placer leurs mots de passe initiaux dans Secrets Manager. `seed.py` crée des identités et patients de démonstration fictifs et ne doit pas être exécuté avec des données opérationnelles.
7. **Logs** : les journaux applicatifs JSON sont écrits sur stdout/stderr pour CloudWatch. Les journaux d’audit applicatifs enregistrent actions, utilisateur, patient et IP; restreindre leur accès et définir leur rétention.

L’application est sans état : les sessions sont signées côté client et ne contiennent pas de dossier médical; PostgreSQL et S3 conservent les données persistantes. Construire l’image avec `docker build`, la publier dans ECR et la déployer sur EC2 avec une configuration injectée depuis Secrets Manager.