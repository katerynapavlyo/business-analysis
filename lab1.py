import os
import csv
import json
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
# ---------------------------------------------------------
# Завдання 1: URL джерела даних (Українська Прем'єр-Ліга)
# ---------------------------------------------------------
BASE_URL = "https://upl.ua/ua"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ---------------------------------------------------------
# Перевірка статичності та завантаження головної сторінки
# ---------------------------------------------------------
response = requests.get(BASE_URL, headers=HEADERS)
response.encoding = 'utf-8'

if response.status_code == 200:
    print("=== Крок 2: Головна сторінка успішно завантажена ===")
    print(response.text[:300])
else:
    print(f"Помилка завантаження: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")

# ---------------------------------------------------------
# Отримання списку підрозділів (клубів) -> TXT та XML
# ---------------------------------------------------------
clubs = []
club_tags = soup.select("a[href*='/clubs/view/']")

seen_urls = set()
for tag in club_tags:
    club_name = tag.text.strip()
    cat_url = urllib.parse.urljoin(BASE_URL, tag["href"])

    if club_name and cat_url not in seen_urls:
        seen_urls.add(cat_url)
        clubs.append({"name": club_name, "url": cat_url})

with open("categories.txt", "w", encoding="utf-8") as f:
    for club in clubs:
        f.write(f"{club['name']}: {club['url']}\n")

root = ET.Element("categories")
for club in clubs:
    cat_el = ET.SubElement(root, "category")
    ET.SubElement(cat_el, "name").text = club["name"]
    ET.SubElement(cat_el, "url").text = club["url"]
tree = ET.ElementTree(root)
tree.write("categories.xml", encoding="utf-8", xml_declaration=True)

print(f"=== Крок 3: Збережено клубів: {len(clubs)} (у categories.txt та categories.xml) ===")

# ---------------------------------------------------------
# Збір об'єктів (гравців/персоналу) з кожної сторінки -> TXT та JSON
# ---------------------------------------------------------
all_players = []
images_to_download = []

for club in clubs[:3]:
    club_res = requests.get(club["url"], headers=HEADERS)
    club_res.encoding = 'utf-8'
    if club_res.status_code != 200:
        continue

    club_soup = BeautifulSoup(club_res.text, "html.parser")
    player_tags = club_soup.select(".player, .squad-item, .team-member, a[href*='/people/view/']")

    for p_tag in player_tags:
        p_name = p_tag.text.strip()
        img_tag = p_tag.find("img") if hasattr(p_tag, 'find') else None

        img_url = ""
        if img_tag and img_tag.get("src"):
            img_url = urllib.parse.urljoin(BASE_URL, img_tag["src"])
            images_to_download.append(img_url)

        if p_name:
            all_players.append({
                "club": club["name"],
                "player_name": p_name,
                "image_url": img_url
            })


with open("items.txt", "w", encoding="utf-8") as f:
    for p in all_players:
        f.write(f"[{p['club']}] {p['player_name']}\n")

with open("items.json", "w", encoding="utf-8") as f:
    json.dump(all_players, f, ensure_ascii=False, indent=4)

print(f"=== Крок 4: Зібрано гравців: {len(all_players)} (у items.txt та items.json) ===")

# ---------------------------------------------------------
# Завантаження зображень -> Папка, TXT та CSV
# ---------------------------------------------------------
os.makedirs("downloaded_images", exist_ok=True)
images_to_download = list(set(images_to_download))

with open("images_list.txt", "w", encoding="utf-8") as f:
    for img_url in images_to_download:
        f.write(f"{img_url}\n")

with open("images_list.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Image URL"])
    for img_url in images_to_download:
        writer.writerow([img_url])

for idx, img_url in enumerate(images_to_download[:5]):
    try:
        img_data = requests.get(img_url, headers=HEADERS).content
        filename = os.path.join("downloaded_images", f"image_{idx + 1}.jpg")
        with open(filename, "wb") as f:
            f.write(img_data)
    except Exception as e:
        print(f"Помилка завантаження фото {img_url}: {e}")

print("=== Крок 5: Зображення збережено в папку downloaded_images, images_list.txt та images_list.csv ===")

# ---------------------------------------------------------
# Збереження всіх даних у базу даних SQLite
# ---------------------------------------------------------
conn = sqlite3.connect("scraped_data.db")
cursor = conn.cursor()

cursor.execute("""
               CREATE TABLE IF NOT EXISTS categories
               (
                   id
                   INTEGER
                   PRIMARY
                   KEY
                   AUTOINCREMENT,
                   name
                   TEXT,
                   url
                   TEXT
               )
               """)

cursor.execute("""
               CREATE TABLE IF NOT EXISTS items
               (
                   id
                   INTEGER
                   PRIMARY
                   KEY
                   AUTOINCREMENT,
                   club
                   TEXT,
                   player_name
                   TEXT,
                   image_url
                   TEXT
               )
               """)

for club in clubs:
    cursor.execute("INSERT INTO categories (name, url) VALUES (?, ?)", (club["name"], club["url"]))

for p in all_players:
    cursor.execute("""
                   INSERT INTO items (club, player_name, image_url)
                   VALUES (?, ?, ?)
                   """, (p["club"], p["player_name"], p["image_url"]))

conn.commit()
conn.close()

print("=== Крок 6: Усі дані успішно збережені в базу даних scraped_data.db ===")