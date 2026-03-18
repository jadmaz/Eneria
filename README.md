# MEWS API → MODBUS TCP SERVER

Ce programme expose le **statut des chambres** de l'API Mews via un serveur Modbus TCP. 
Les données peuvent être lues par des outils de supervision (SCADA, PLC, automates, etc.).

## 🎯 Fonctionnement

Le programme récupère **directement le statut de chaque chambre** depuis l'API Mews:
- ✅ **Clean** - Propre et disponible
- 🟡 **Dirty** - Sale, besoin de nettoyage
- 🔵 **Inspected** - Inspectée
- ⛔ **OutOfService** - Hors service
- ⛔ **OutOfOrder** - Hors service (maintenance)

**Aucune** analyse de réservations nécessaire - le statut vient directement de l'API.

## 🚀 Démarrage rapide

### Installation
```bash
pip install requests pymodbus
```

### Lancement du serveur
```bash
python program.py
```

Le serveur démarre sur **0.0.0.0:5020** et se met à jour automatiquement toutes les 5 minutes.

## 📊 Architecture Modbus

### Unit IDs (Slaves)
- **Chaque chambre = 1 Unit ID** (le mapping est persistant dans `rooms_mapping.json`)
- Les Unit IDs ne changent JAMAIS (même si la chambre est supprimée de l'API)
- Les nouveaux Unit IDs sont attribués automatiquement aux nouvelles chambres

### Structure des registres (par Unit ID)

Chaque Unit ID expose 10 registres principaux:

| Registre | Description | Valeurs |
|----------|-------------|---------|
| **0** | Statut de la chambre | 0 = Unknown<br>1 = Clean (propre)<br>2 = Dirty (sale)<br>3 = Inspected<br>4 = OutOfService<br>5 = OutOfOrder |
| **1** | Existe dans l'API | 1 = chambre active dans Mews<br>0 = chambre supprimée de l'API |
| **2** | Numéro de chambre | Numéro extrait du nom de la chambre |
| **3** | Erreur API | 0 = connexion OK<br>1 = erreur de connexion API |
| **4** | Heure de MAJ | Heure de la dernière mise à jour (0-23) |
| **5** | Minute de MAJ | Minute de la dernière mise à jour (0-59) |
| **6** | Total Clean | Nombre total de chambres propres |
| **7** | Total Dirty | Nombre total de chambres sales |
| **8** | Total Inspected | Nombre total de chambres inspectées |
| **9** | Total Out | Nombre total de chambres hors service |

### Types de registres
- **Holding Registers (HR)** : Fonction 3 et 16
- **Input Registers (IR)** : Fonction 4 (lecture seule)

## 🔧 Configuration

### Modifier le port Modbus
Dans `program.py`:
```python
MODBUS_PORT = 5020  # Changer pour 502 en production (nécessite droits admin)
```

### Modifier l'intervalle de mise à jour
```python
POLLING_INTERVAL = 300  # Secondes (300 = 5 minutes)
```

### Changer les credentials API
```python
CLIENT_TOKEN = "VOTRE_CLIENT_TOKEN"
ACCESS_TOKEN = "VOTRE_ACCESS_TOKEN"
```

## 📖 Exemples d'utilisation

### Lire le statut d'une chambre (Unit ID 1)

**Avec pymodbus (Python)**:
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('127.0.0.1', port=5020)
client.connect()

# Lire les registres 0-9 pour la chambre Unit ID 1
result = client.read_holding_registers(0, 10, unit=1)

if result.isError():
    print("Erreur de lecture")
else:
    # Mapping des statuts
    STATUS_NAMES = {
        0: "Unknown",
        1: "Clean",
        2: "Dirty",
        3: "Inspected",
        4: "OutOfService",
        5: "OutOfOrder"
    }
    
    status_code = result.registers[0]
    status_name = STATUS_NAMES.get(status_code, "Unknown")
    existe = result.registers[1]
    numero_chambre = result.registers[2]
    total_clean = result.registers[6]
    total_dirty = result.registers[7]
    
    print(f"Chambre {numero_chambre}:")
    print(f"  Statut: {status_name}")
    print(f"  Total chambres propres: {total_clean}")
    print(f"  Total chambres sales: {total_dirty}")

client.close()
```

### Lire toutes les chambres Clean (propres)

```python
from pymodbus.client import ModbusTcpClient
import json

# Charger le mapping pour connaître les correspondances
with open('rooms_mapping.json', 'r') as f:
    mapping = json.load(f)['mapping']

# Inverser le mapping: {unit_id: room_id}
unit_to_room = {v: k for k, v in mapping.items()}

client = ModbusTcpClient('127.0.0.1', port=5020)
client.connect()

chambres_propres = []

for unit_id in range(1, len(mapping) + 1):
    result = client.read_holding_registers(0, 3, unit=unit_id)
    
    if not result.isError():
        status_code = result.registers[0]
        existe = result.registers[1]
        numero = result.registers[2]
        
        # Clean = statut 1
        if status_code == 1 and existe == 1:
            chambres_propres.append({
                'unit_id': unit_id,
                'numero': numero,
                'room_id': unit_to_room.get(unit_id)
            })

print(f"Chambres propres (Clean): {len(chambres_propres)}")
for ch in chambres_propres:
    print(f"  Unit ID {ch['unit_id']}: Chambre {ch['numero']}")

client.close()
```

### Monitoring continu des statuts

```python
from pymodbus.client import ModbusTcpClient
import time

client = ModbusTcpClient('127.0.0.1', port=5020)
client.connect()

while True:
    # Lire les registres 6-9 du Unit ID 1 pour avoir les totaux globaux
    result = client.read_holding_registers(6, 4, unit=1)
    
    if not result.isError():
        total_clean = result.registers[0]
        total_dirty = result.registers[1]
        total_inspected = result.registers[2]
        total_out = result.registers[3]
        
        print(f"État: {total_clean} propres / {total_dirty} sales / "
              f"{total_inspected} inspectées / {total_out} hors service")
    
    time.sleep(60)  # Vérifier chaque minute
```

## 📁 Fichiers générés

### `rooms_mapping.json`
Mapping persistant entre Room IDs (UUID Mews) et Unit IDs Modbus.

```json
{
  "timestamp": "2026-03-04T15:11:57.123456",
  "description": "Mapping persistant Unit ID <-> Chambre (ne change jamais)",
  "mapping": {
    "abc123-uuid-room1": 1,
    "def456-uuid-room2": 2,
    "ghi789-uuid-room3": 3
  }
}
```

⚠️ **NE PAS SUPPRIMER CE FICHIER** - Il assure la cohérence des Unit IDs entre les redémarrages.

## 🛠️ Outils compatibles

Le serveur Modbus est compatible avec:
- **SCADA**: WinCC, Ignition, Wonderware, etc.
- **PLC**: Siemens, Allen-Bradley, Schneider, etc.
- **Logiciels de test**: ModbusPoll, QModMaster, mbpoll
- **Bibliothèques**: pymodbus (Python), node-modbus (Node.js), modbus-tk, etc.

## 🔍 Dépannage

### Le serveur ne démarre pas
- Vérifier que le port 5020 n'est pas déjà utilisé
- Sur Windows, le port 502 nécessite des droits administrateur

### Erreurs API Mews
- Vérifier les credentials CLIENT_TOKEN et ACCESS_TOKEN
- Vérifier la connexion Internet
- Le serveur continue de fonctionner avec les dernières données connues

### Tester la connexion Modbus
```bash
# Avec mbpoll (Linux/Mac)
mbpoll -a 1 -r 0 -c 10 -t 3 127.0.0.1 -p 5020

# Avec Python
python -m pymodbus.console tcp --host 127.0.0.1 --port 5020
```

### Interpréter les codes de statut

| Code | Statut | Signification | Action recommandée |
|------|--------|---------------|-------------------|
| 0 | Unknown | Statut inconnu | Vérifier l'API |
| 1 | Clean | Propre et prête | ✅ Chambre utilisable |
| 2 | Dirty | Sale, à nettoyer | 🧹 Envoyer l'entretien ménager |
| 3 | Inspected | Inspectée | ✅ Chambre vérifiée |
| 4 | OutOfService | Hors service | ⛔ Ne pas assigner |
| 5 | OutOfOrder | En maintenance | 🔧 Maintenance en cours |

## 📝 Logs

Les logs affichent:
- Démarrage et mapping des chambres
- Mises à jour périodiques
- Erreurs de connexion API
- Total chambres par statut (Clean, Dirty, Inspected, Out of Service)

Exemple:
```
2026-03-04 15:11:59,127 - INFO - ✅ Mise à jour terminée | Clean: 150, Dirty: 30, Inspected: 15, Out: 5, Erreur API: 0
```

## 🔐 Sécurité

⚠️ **Production**: 
- Ne PAS exposer le port Modbus sur Internet
- Utiliser un firewall pour limiter l'accès
- Stocker les credentials dans des variables d'environnement
- Utiliser HTTPS/VPN pour accès distant

## 📄 Licence

Ce logiciel est fourni tel quel sans garantie.
