# SEC Admin Backend

Backend d'administration pour SEC. Il est separe du backend MQTT maison et sert a gerer :

- authentification admin et client ;
- refresh token et logout ;
- mot de passe oublie avec email de reset ;
- verification d'email ;
- changement de mot de passe ;
- audit minimal des evenements auth ;
- comptes administrateurs ;
- clients/utilisateurs ;
- maisons des clients ;
- compteurs electriques ;
- energie chargee dans les compteurs ;
- transactions de paiement/recharge.

## Architecture

```text
Flutter admin / mobile client
        |
        v
FastAPI admin backend
        |
        v
MySQL
```

Conteneurs Docker :

- `sec-adm-mysql` : base MySQL 8.4 ;
- `sec-adm-api` : serveur FastAPI.

Ports locaux :

- API : `http://localhost:8100`
- Swagger : `http://localhost:8100/docs`
- MySQL : `localhost:3307`

## Lancement

Copier l'exemple d'environnement si besoin :

```powershell
Copy-Item .env.example .env
```

```powershell
cd "C:\Flutter Projects\sec-adm-backend"
docker-compose up -d --build
```

Verifier :

```powershell
Invoke-RestMethod http://localhost:8100/health
```

Reponse attendue :

```json
{
  "status": "ok",
  "database": "mysql"
}
```

Voir les logs :

```powershell
docker-compose logs -f api
docker-compose logs -f mysql
```

Arreter :

```powershell
docker-compose down
```

Supprimer aussi les donnees MySQL :

```powershell
docker-compose down -v
```

## Variables d'environnement

Les principales variables sont dans `.env.example` :

```text
MYSQL_DATABASE=sec_adm
MYSQL_USER=sec_adm_user
MYSQL_PASSWORD=sec_adm_password
MYSQL_ROOT_PASSWORD=sec_root_password
DATABASE_URL=mysql+pymysql://sec_adm_user:sec_adm_password@mysql:3306/sec_adm
JWT_SECRET_KEY=change-this-secret-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=30
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
FRONTEND_URL=http://localhost:3000
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@sec.local
SMTP_USE_TLS=true
PAWAPAY_BASE_URL=https://api.sandbox.pawapay.io
PAWAPAY_API_TOKEN=
PAWAPAY_CALLBACK_URL=
PAWAPAY_DEFAULT_COUNTRY=COD
PAWAPAY_DEFAULT_CURRENCY=CDF
PAWAPAY_DEFAULT_CORRESPONDENT=VODACOM_MPESA_COD
FIREBASE_CREDENTIALS_PATH=
FIREBASE_PROJECT_ID=
FIRST_ADMIN_EMAIL=admin@sec.local
FIRST_ADMIN_PASSWORD=admin12345
FIRST_ADMIN_FULL_NAME=SEC Admin
```

## Notifications push telephone

Le backend peut enregistrer les tokens FCM des telephones connectes et envoyer
des push au client pendant les recharges/paiements.

Endpoints client :

```text
POST   /push-tokens/me
GET    /push-tokens/me
DELETE /push-tokens/me/{tokenId}
```

Exemple d'enregistrement par l'application Flutter :

```json
{
  "token": "FCM_DEVICE_TOKEN",
  "platform": "android",
  "deviceId": "telephone-principal"
}
```

Pour activer l'envoi reel des push :

1. Creer un projet Firebase.
2. Creer une cle de compte de service Firebase Admin.
3. Copier le fichier JSON dans `firebase/service-account.json`.
4. Renseigner :

```text
FIREBASE_CREDENTIALS_PATH=/app/firebase/service-account.json
FIREBASE_PROJECT_ID=ton-projet-firebase
```

Si `FIREBASE_CREDENTIALS_PATH` est vide, les endpoints restent disponibles,
mais l'envoi FCM est ignore proprement. Cela permet de continuer les paiements
et les tests sans Firebase.

Important : `.env` est ignore par Git. Ne jamais pousser les vrais secrets.

## Compte admin par defaut

Au premier demarrage, l'API cree un administrateur :

```text
email: admin@sec.local
password: admin12345
```

Ces valeurs viennent de `.env`. Elles doivent etre changees avant tout usage reel.

## Authentification

Login admin :

```http
POST /auth/admin/login
```

Body :

```json
{
  "email": "admin@sec.local",
  "password": "admin12345"
}
```

Login client :

```http
POST /auth/client/login
```

La reponse contient un JWT :

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "tokenType": "bearer",
  "role": "super_admin",
  "userId": 1,
  "email": "admin@sec.local"
}
```

Ensuite utiliser :

```text
Authorization: Bearer <accessToken>
```

Flux auth complets :

```text
POST /auth/client/register
POST /auth/admin/login
POST /auth/client/login
POST /auth/refresh
POST /auth/logout
POST /auth/forgot-password
POST /auth/reset-password
POST /auth/change-password
POST /auth/verify-email
POST /auth/resend-verification
GET  /auth/admin/me
GET  /auth/client/me
```

Register client public :

```http
POST /auth/client/register
```

Body :

```json
{
  "email": "client@example.com",
  "phone": "+243810000000",
  "fullName": "Client Demo",
  "password": "client12345"
}
```

L'API :

```text
1. verifie que l'email et le telephone sont uniques ;
2. cree le client ;
3. hash le mot de passe ;
4. cree un token de verification email ;
5. envoie l'email de verification ;
6. retourne accessToken et refreshToken.
```

Exemple PowerShell :

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8100/auth/client/register" `
  -ContentType "application/json" `
  -Body '{
    "email": "client@example.com",
    "phone": "+243810000000",
    "fullName": "Client Demo",
    "password": "client12345"
  }'
```

Mot de passe oublie :

```http
POST /auth/forgot-password
```

Body :

```json
{
  "email": "client@example.com",
  "actorType": "client"
}
```

L'API genere un token temporaire, stocke uniquement son hash dans MySQL, puis
envoie un lien vers :

```text
{FRONTEND_URL}/reset-password?actorType=client&token=...
```

En mode developpement, si `SMTP_HOST` est vide, l'email est affiche dans les
logs du conteneur `api`.

Reinitialiser le mot de passe :

```http
POST /auth/reset-password
```

```json
{
  "token": "TOKEN_RECU_PAR_EMAIL",
  "newPassword": "nouveauMotDePasse123"
}
```

Verification email :

```http
POST /auth/resend-verification
POST /auth/verify-email
```

Changement de mot de passe connecte :

```http
POST /auth/change-password
Authorization: Bearer <accessToken>
```

Refresh et logout :

```http
POST /auth/refresh
POST /auth/logout
```

Refresh token :

```json
{
  "refreshToken": "REFRESH_TOKEN"
}
```

Logout :

```json
{
  "refreshToken": "REFRESH_TOKEN"
}
```

Le logout marque la session refresh comme revoquee dans `refresh_sessions`.

## Endpoints principaux

Admins :

```text
GET  /admins
POST /admins
```

Clients :

```text
GET   /clients
POST  /clients
GET   /clients/me
GET   /clients/{clientId}
PATCH /clients/{clientId}
```

Maisons :

```text
GET    /homes
POST   /homes
GET    /homes/me
GET    /homes/{homeId}
PATCH  /homes/{homeId}
DELETE /homes/{homeId}
```

Compteurs :

```text
GET   /meters
GET   /meters/{meterId}
PATCH /meters/{meterId}
```

Transactions :

```text
GET  /transactions
GET  /transactions/me
GET  /transactions/{reference}
POST /transactions/homes/{homeId}/recharge
POST /transactions/homes/{homeId}/pawapay/recharge
POST /transactions/{reference}/sync
POST /transactions/pawapay/callback
POST /transactions/admin/homes/{homeId}/recharge
```

## Exemple de flux complet

Parcours admin :

1. Login admin.
2. Creer un client, ou laisser le client s'inscrire lui-meme avec `/auth/client/register`.
3. Creer une maison pour ce client avec son compteur.
4. Consulter les compteurs et transactions.

Parcours client :

1. Register ou login.
2. Verifier son email.
3. Consulter ses maisons avec `/homes/me`.
4. Recharger son compteur via pawaPay sandbox.
5. Consulter ses transactions avec `/transactions/me`.
6. Rafraichir une transaction en attente avec `/transactions/{reference}/sync`.

Effet d'une recharge :

```text
paiement pawaPay confirme
  -> energy_kwh calcule depuis amount / energyPricePerKwh
  -> meters.energy_balance_kwh augmente
  -> meters.total_loaded_kwh augmente
  -> meters.total_paid_amount augmente
```

## Creer un client

```powershell
$token = "<ADMIN_TOKEN>"

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8100/clients" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{
    "email": "client@example.com",
    "phone": "+243810000000",
    "fullName": "Client Demo",
    "password": "client12345"
  }'
```

## Creer une maison avec compteur

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8100/homes" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{
    "clientId": 1,
    "name": "Maison principale",
    "address": "Kinshasa",
    "city": "Kinshasa",
    "country": "RDC",
    "currency": "FC",
    "energyPricePerKwh": 500,
    "meter": {
      "meterNumber": "SEC-METER-0001",
      "provider": "SEC",
      "initialEnergyKwh": 0
    }
  }'
```

## Recharger le compteur avec pawaPay sandbox

Cote client :

```powershell
$clientToken = "<CLIENT_TOKEN>"

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8100/transactions/homes/1/pawapay/recharge" `
  -Headers @{ Authorization = "Bearer $clientToken" } `
  -ContentType "application/json" `
  -Body '{
    "amount": 10000,
    "payerPhone": "243810000000"
  }'
```

Le backend cree une transaction `pending`, appelle pawaPay sandbox, puis attend
la confirmation. Si le prix est `500 FC/kWh`, un paiement confirme de
`10000 FC` charge :

```text
10000 / 500 = 20 kWh
```

Verifier ou synchroniser le statut :

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8100/transactions/SEC-PAWA-REFERENCE/sync" `
  -Headers @{ Authorization = "Bearer $clientToken" } `
  -ContentType "application/json" `
  -Body '{}'
```

Callback pawaPay :

```text
POST /transactions/pawapay/callback
```

Pour que pawaPay atteigne ton backend local, `PAWAPAY_CALLBACK_URL` doit etre
une URL publique qui pointe vers :

```text
https://ton-domaine-ou-tunnel/transactions/pawapay/callback
```

En local, tu peux laisser `PAWAPAY_CALLBACK_URL` vide et utiliser la route
`/transactions/{reference}/sync` pour interroger pawaPay depuis l'application.

La table `transactions` garde l'historique, et la table `meters` garde :

```text
energy_balance_kwh
total_loaded_kwh
total_paid_amount
last_loaded_at
```

## Tables MySQL

- `admins` : administrateurs ;
- `clients` : utilisateurs/clients ;
- `password_reset_tokens` : tokens de reset hashes, expiration, usage unique ;
- `email_verification_tokens` : tokens de verification email hashes ;
- `refresh_sessions` : sessions refresh token revocables ;
- `auth_audit_logs` : historique minimal des evenements auth ;
- `homes` : maisons des clients ;
- `meters` : compteurs electriques des maisons ;
- `transactions` : paiements et recharges d'energie.

## Modele des donnees

Relation principale :

```text
clients 1--N homes
homes   1--1 meters
homes   1--N transactions
meters  1--N transactions
```

`clients` :

```text
id, email, phone, full_name, password_hash,
is_active, email_verified, created_at, updated_at
```

`homes` :

```text
id, client_id, name, address, city, country,
currency, energy_price_per_kwh, created_at, updated_at
```

`meters` :

```text
id, home_id, meter_number, provider,
energy_balance_kwh, total_loaded_kwh, total_paid_amount,
status, last_loaded_at
```

`transactions` :

```text
id, reference, client_id, home_id, meter_id,
amount, currency, energy_kwh, payment_method,
provider_reference, payment_provider, provider_deposit_id,
provider_status, payer_phone, failure_reason,
callback_payload, status, created_at, paid_at
```

## Maintenance

Entrer dans MySQL :

```powershell
docker-compose exec mysql mysql -u sec_adm_user -psec_adm_password sec_adm
```

Lister les tables :

```sql
SHOW TABLES;
```

Voir les derniers paiements :

```sql
SELECT reference, client_id, home_id, amount, energy_kwh, status, paid_at
FROM transactions
ORDER BY id DESC
LIMIT 10;
```

Voir les logs email de developpement :

```powershell
docker-compose logs -f api
```

## Remarques importantes

- Ce backend admin est separe du backend MQTT `sec-backend`.
- Ici on commence l'authentification et la partie paiement/compteur client.
- Les paiements client passent par pawaPay sandbox avec statut `pending`, `paid` ou `failed`.
- Le compteur est credite uniquement quand pawaPay confirme le paiement.
- Pour la production, il faudra remplacer les secrets sandbox, activer TLS, securiser les callbacks et renforcer les roles.
