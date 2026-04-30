# Eneria - Guide installation et utilisation CPT Tools

Ce programme connecte l'API MEWS et publie l'etat d'occupation des chambres en Modbus TCP.

## Ce que fait le programme

Pour chaque chambre MEWS, le serveur expose une valeur Modbus:

- 1 = chambre occupee
- 0 = chambre disponible

Chaque chambre est associee a un Unit ID Modbus fixe (mapping persistant).

## Installation

Dans le dossier du projet, executer:

```bat
setup.bat
```

Ce script va:

- creer l'environnement Python `.venv`
- installer les dependances necessaires (`requests`, `pymodbus`)
- preparer le programme
- creer le fichier `.env` s'il n'existe pas

Cette etape doit etre faite une seule fois.

## Configuration du .env

Apres l'installation, ouvrir le fichier `.env` et renseigner:

```env
MEWS_CLIENT_TOKEN=VOTRE_CLIENT_TOKEN
MEWS_ACCESS_TOKEN=VOTRE_ACCESS_TOKEN
MEWS_STAY_SERVICE_ID=ID_SERVICE_HEBERGEMENT
```

Parametres optionnels:

```env
MEWS_BASE_URL=https://api.mews.com/api/connector/v1
MODBUS_PORT=5020
POLLING_INTERVAL=300
SHOW_UI=true
```


## Demarrage du serveur

Demarrage recommande (interface incluse):

```bat
start.bat
```

Au lancement via `start.bat`, l'application ouvre l'interface locale avec le statut des chambres.

La fermeture de la fenetre demande une confirmation car elle arrete aussi le serveur Modbus et les appels API.

## Configuration du serveur dans CPT Tools

Ce guide explique comment configurer CPT Tools pour lire les registres Modbus du serveur Eneria.

### 1. Creer le reseau Modbus

Dans CPT Tools:

- ajouter un nouvel element `ModbusTCPNetwork`

Ce reseau represente la connexion Modbus TCP.

### 2. Ajouter le device Modbus

Dans `ModbusTCPNetwork`, ajouter:

- `ModbusTCPDevice`
- mettre `enable = true`

Configurer les parametres du device:

| Parametre | Valeur |
|---|---|
| IP Address | Adresse IP de l'ordinateur qui execute le serveur Modbus. Pour la trouver: ouvrir cmd, taper `ipconfig`, puis lire la ligne IPv4 de la carte reseau utilisee. |
| enable | true |
| Port | 5020 (ou la valeur de `MODBUS_PORT` dans `.env`) |
| address | Unit ID de la chambre (voir `rooms_mapping.json`) |

Important:

- 1 chambre = 1 Unit ID
- les Unit IDs sont dans `rooms_mapping.json`

### 3. Ajouter les registres

Dans `ModbusTCPDevice`, ajouter des elements:

- `ModbusHoldingRegister`

Configurer chaque registre avec:

| Parametre | Valeur |
|---|---|
| address | 0 |
| enable | true |

### 4. Structure des registres

Par Unit ID (chambre), le serveur expose:

| Registre | Description |
|---|---|
| 0 | Occupation (0 = disponible, 1 = occupee) |

Notes d'adressage selon l'outil:

- certains clients utilisent l'adresse `0`
- d'autres affichent `40001`
- `0` et `40001` pointent le meme registre logique

### 5. Exemple de lecture dans CPT Tools

1. Selectionner une chambre (Unit ID via `address` du device)
2. Lire le registre `0`
3. Interpreter la valeur:
- 0: disponible
- 1: occupee

## Demarrage du dashboard sans terminal

Pour lancer le dashboard manuellement sans aucune fenetre de terminal:

```vbs
start_ui.vbs
```

Double-cliquer sur ce fichier pour ouvrir **seulement le dashboard** (mode interface utilisateur pur).

## Lancer le dashboard en startup (sans terminal)

Pour que le dashboard se lance automatiquement au démarrage **sans aucune fenetre en arriere-plan**:

### 1. Ouvrir le Planificateur de taches

- Appuyer sur `Windows + R`
- Taper: `taskschd.msc`
- Valider

### 2. Creer une nouvelle tache

- Dans le menu de droite, cliquer sur "Creer une tache..."
- Donner un nom: `Eneria-Dashboard-Startup`
- Cocher "Executer avec les autorisations les plus elevees"

### 3. Configurer le declencheur

- Aller a l'onglet "Declencheurs"
- Cliquer sur "Nouveau..."
- Selectionner "A la connexion"
- Cliquer sur "OK"

### 4. Configurer l'action pour le dashboard sans terminal

- Aller a l'onglet "Actions"
- Cliquer sur "Nouveau..."
- **Programme**: `wscript.exe`
- **Arguments**: `"C:\chemin\vers\Eneria\start_ui.vbs"` (remplacer par votre chemin reel complet)
- Cliquer sur "OK"

### 5. Finaliser

- Cliquer sur "OK" pour creer la tache

Avec cette configuration, **seul le dashboard s'affichera** a la connexion, sans terminal.

### Verification

La tache est maintenant active. Pour verifier:

1. Ouvrir le Planificateur de taches (`Windows + R` > `taskschd.msc`)
2. Chercher `Eneria-Dashboard-Startup` dans la liste
3. Verifier que le statut est `Actif`

Le dashboard se lancera automatiquement a la prochaine connexion, completement silencieux.