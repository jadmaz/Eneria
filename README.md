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
```

Parametres optionnels:

```env
MEWS_BASE_URL=https://api.mews.com/api/connector/v1
MODBUS_PORT=5020
POLLING_INTERVAL=300
MOCK_MODE=false
MOCK_ROOM_COUNT=10
```

## Mode test (valeurs mock)

Si vous voulez tester sans API MEWS, activez le mode mock dans `.env`:

```env
MOCK_MODE=true
MOCK_ROOM_COUNT=10
```

Comportement du mode mock:

- aucune connexion a l'API MEWS
- generation automatique de chambres fictives
- changement des valeurs d'occupation a chaque cycle de mise a jour
- registre Modbus identique: `0` (0 = disponible, 1 = occupee)

Le mapping des Unit IDs est conserve dans `rooms_mapping.json` comme en mode normal.

## Demarrage du serveur

Mode normal (fenetre visible):

```bat
start.bat
```


### Utiliser start_hidden.vbs

Le fichier `start_hidden.vbs` lance `start_silent.bat` en mode cache (sans fenetre visible).

Utilisation manuelle:

1. Verifier que `setup.bat` a deja ete execute
2. Double-cliquer sur `start_hidden.vbs`

Utilisation au demarrage Windows:

1. Appuyer sur Win + R
2. Taper `shell:startup`
3. Creer un raccourci de `start_hidden.vbs`
4. Placer ce raccourci dans le dossier ouvert

Au prochain redemarrage, le serveur se lancera automatiquement en arriere-plan.

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