import sys, re

test_lines = [
    "Chapter 5. Maniacal Mints / МАНИАКАЛЬНАЯ МЯТА",
    "Глава 6. Caramel Comforts - Карамельный Комфорт",
    "4. Peanut Butter Panaceas - Панацея Из Арахисового Масла",
    "3. Сливочное Рандеву На Двоих / Double Fudge Rendezvous",
    "ГЛАВА 6.2",
    "Глава 6",
    "В полночь я стояла у своей кухонной двери, судорожно вздыхая.",
    "Остаток недели прошел в волшебном тумане, сотканном из беседки, печений и влажных темных волос."
]

def is_banner(line: str) -> bool:
    line = line.strip()
    if not line:
        return True
    if len(line) > 130:
        return False
    # Matches like 'Chapter 5. ...', 'Глава 6. ...', '4. ...'
    if re.match(r'^(?:Chapter|Глава)?\s*\d+\.?\s*[A-Za-z\s]+[-–—/]\s*[\w\s]+$', line, re.I):
        return True
    if re.match(r'^(?:Chapter|Глава)?\s*\d+\.?\s*[\w\s]+[-–—/]\s*[A-Za-z\s]+$', line, re.I):
        return True
    if re.match(r'^[A-Za-z\s]+[-–—/]\s*[\w\s]+$', line) and len(line) < 100:
        return True
    if re.match(r'^[\w\s]+[-–—/]\s*[A-Za-z\s]+$', line) and len(line) < 100:
        return True
    if re.match(r'^(?:ГЛАВА|Глава|CHAPTER|Chapter)\s*\d+(\.\d+)?$', line, re.I):
        return True
    if line.startswith("Wide Awake."):
        return True
    return False

for l in test_lines:
    print(f"[{is_banner(l)}] -> {l}")
