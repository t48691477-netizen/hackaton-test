#!/usr/bin/env python3
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFont

EQUIPMENT_DATA = [
    {
        "id": "pump-ams-pcp60s12-01",
        "aliases": ["pump-ams-pcp60s12-3-01-1"],
        "name": "Винтовой насосный агрегат AMS PCP60S12/3 №1",
        "serial_number": "21031004-1",
        "location": "Технологический цех №1, Насосная станция №1",
        "installation_date": "2023-04-15",
        "component_age": "1 год 7 месяцев",
        "last_maintenance_date": "2026-04-10",
        "status": "operational",
        "components": [
            {
                "id": "comp_pump_ams_01",
                "name": "Винтовой насос AMS PCP60S12/3 01 Ex B1 HNBR DTS",
                "type": "Винтовой объемный насос",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.8,
            },
            {
                "id": "comp_motor_ams_01",
                "name": "Электродвигатель BRA160M4 F5У1 (11 кВт, 1460 об/мин, зав. № 230201068)",
                "type": "Взрывозащищенный привод 1Ex d IIB T4 Gb",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_reducer_ams_01",
                "name": "Цилиндрический редуктор WXRF87-AM160 (i=5.30, 910 Н·м, зав. № SAL023020084_001002)",
                "type": "Механический редукторный узел",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.4,
            },
            {
                "id": "comp_tpp_ams_01",
                "name": "Прецизионный термопреобразователь ПТ 0304-ВТ",
                "type": "Датчик температуры подшипников",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.2,
            },
        ],
    },
    {
        "id": "pump-ams-pcp60s12-02",
        "aliases": ["pump-ams-pcp60s12-3-01-2"],
        "name": "Винтовой насосный агрегат AMS PCP60S12/3 №2",
        "serial_number": "21031004-2",
        "location": "Технологический цех №1, Насосная станция №1",
        "installation_date": "2023-04-15",
        "component_age": "1 год 7 месяцев",
        "last_maintenance_date": "2026-04-12",
        "status": "operational",
        "components": [
            {
                "id": "comp_pump_ams_02",
                "name": "Винтовой насос AMS PCP60S12/3 01 Ex B1 HNBR DTS",
                "type": "Винтовой объемный насос",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.8,
            },
            {
                "id": "comp_motor_ams_02",
                "name": "Электродвигатель BRA160M4 F5У1 (11 кВт, 1460 об/мин, зав. № 230201069)",
                "type": "Взрывозащищенный привод 1Ex d IIB T4 Gb",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_reducer_ams_02",
                "name": "Цилиндрический редуктор WXRF87-AM160 (i=5.30, 910 Н·м, зав. № SAL023020084_001003)",
                "type": "Механический редукторный узел",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.4,
            },
            {
                "id": "comp_tpp_ams_02",
                "name": "Прецизионный термопреобразователь ПТ 0304-ВТ",
                "type": "Датчик температуры подшипников",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.2,
            },
        ],
    },
    {
        "id": "pump-ams-pcp60s12-03",
        "aliases": ["pump-ams-pcp60s12-3-01-3"],
        "name": "Винтовой насосный агрегат AMS PCP60S12/3 №3",
        "serial_number": "21031004-3",
        "location": "Технологический цех №1, Насосная станция №1",
        "installation_date": "2023-04-15",
        "component_age": "1 год 7 месяцев",
        "last_maintenance_date": "2026-04-15",
        "status": "operational",
        "components": [
            {
                "id": "comp_pump_ams_03",
                "name": "Винтовой насос AMS PCP60S12/3 01 Ex B1 HNBR DTS",
                "type": "Винтовой объемный насос",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.8,
            },
            {
                "id": "comp_motor_ams_03",
                "name": "Электродвигатель BRA160M4 F5У1 (11 кВт, 1460 об/мин, зав. № 230201067)",
                "type": "Взрывозащищенный привод 1Ex d IIB T4 Gb",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_reducer_ams_03",
                "name": "Цилиндрический редуктор WXRF87-AM160 (i=5.30, 910 Н·м, зав. № SAL023020084_001004)",
                "type": "Механический редукторный узел",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.4,
            },
            {
                "id": "comp_tpp_ams_03",
                "name": "Прецизионный термопреобразователь ПТ 0304-ВТ",
                "type": "Датчик температуры подшипников",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.2,
            },
        ],
    },
    {
        "id": "pump-ams-pcp60s12-04",
        "aliases": ["pump-ams-pcp60s12-3-01-4"],
        "name": "Винтовой насосный агрегат AMS PCP60S12/3 №4",
        "serial_number": "21031004-4",
        "location": "Технологический цех №1, Насосная станция №1",
        "installation_date": "2023-04-15",
        "component_age": "1 год 7 месяцев",
        "last_maintenance_date": "2026-04-18",
        "status": "operational",
        "components": [
            {
                "id": "comp_pump_ams_04",
                "name": "Винтовой насос AMS PCP60S12/3 01 Ex B1 HNBR DTS",
                "type": "Винтовой объемный насос",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.8,
            },
            {
                "id": "comp_motor_ams_04",
                "name": "Электродвигатель BRA160M4 F5У1 (11 кВт, 1460 об/мин, зав. № 230201070)",
                "type": "Взрывозащищенный привод 1Ex d IIB T4 Gb",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_reducer_ams_04",
                "name": "Цилиндрический редуктор WXRF87-AM160 (i=5.30, 910 Н·м, зав. № SAL023020084_001001)",
                "type": "Механический редукторный узел",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.4,
            },
            {
                "id": "comp_tpp_ams_04",
                "name": "Прецизионный термопреобразователь ПТ 0304-ВТ",
                "type": "Датчик температуры подшипников",
                "installation_date": "2023-04-15",
                "age_months": 19,
                "criticality_factor": 1.2,
            },
        ],
    },
    {
        "id": "pump-pedrollo-fcr-15-30",
        "aliases": ["pump-fcr-15-30"],
        "name": "Центробежный многоступенчатый электронасос Pedrollo FCR 15-30",
        "serial_number": "SN-FCR-2023-0482",
        "location": "Насосная станция оборотного водоснабжения №2",
        "installation_date": "2023-05-10",
        "component_age": "1 год 6 месяцев",
        "last_maintenance_date": "2026-05-20",
        "status": "operational",
        "components": [
            {
                "id": "comp_fcr_casing",
                "name": "Всасывающий и напорный корпус насоса",
                "type": "Корпус из нержавеющей стали AISI 304, резьба ISO 228/1, Pmax 12 бар",
                "installation_date": "2023-05-10",
                "age_months": 18,
                "criticality_factor": 1.4,
            },
            {
                "id": "comp_fcr_impellers",
                "name": "Рабочие колеса и диафрагмы",
                "type": "Многоступенчатая гидравлическая группа AISI 304 (до 48 м³/ч, напор до 120 м)",
                "installation_date": "2023-05-10",
                "age_months": 18,
                "criticality_factor": 1.7,
            },
            {
                "id": "comp_fcr_shaft",
                "name": "Вал насоса",
                "type": "Вал из нержавеющей стали AISI 316L",
                "installation_date": "2023-05-10",
                "age_months": 18,
                "criticality_factor": 1.6,
            },
            {
                "id": "comp_fcr_seal",
                "name": "Механическое торцевое уплотнение FN-KU-24",
                "type": "Торцевое уплотнение Ø 24 мм (керамика / графит / NBR, ISO 3069)",
                "installation_date": "2023-05-10",
                "age_months": 18,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_fcr_motor",
                "name": "Электродвигатель трехфазный IE3",
                "type": "Асинхронный двигатель 230/400 В, 50 Гц, 2900 об/мин, IP55, класс F",
                "installation_date": "2023-05-10",
                "age_months": 18,
                "criticality_factor": 1.5,
            },
        ],
    },
    {
        "id": "pump-cns-38-220",
        "aliases": ["pump_cns_38_220"],
        "name": "Центробежный секционный насос ЦНС 38-220",
        "serial_number": "SN-CNS-2021-38220",
        "location": "Цех подготовки и перекачки нефти, Блок №2",
        "installation_date": "2021-06-10",
        "component_age": "3 года 5 месяцев",
        "last_maintenance_date": "2026-06-15",
        "status": "operational",
        "components": [
            {
                "id": "comp_cns_rotor",
                "name": "Ротор многосекционный с рабочими колесами",
                "type": "Вращающийся гидродинамический узел (сталь 40Х13)",
                "installation_date": "2021-06-10",
                "age_months": 41,
                "criticality_factor": 1.8,
            },
            {
                "id": "comp_cns_casing",
                "name": "Секционный корпус и направляющие аппараты",
                "type": "Напорный корпус секционного типа (чугун СЧ20)",
                "installation_date": "2021-06-10",
                "age_months": 41,
                "criticality_factor": 1.5,
            },
            {
                "id": "comp_cns_seals",
                "name": "Торцевые уплотнения вала",
                "type": "Одинарное торцевое уплотнение карбид кремния",
                "installation_date": "2021-06-10",
                "age_months": 41,
                "criticality_factor": 1.6,
            },
            {
                "id": "comp_cns_bearings",
                "name": "Подшипниковые опоры скольжения",
                "type": "Опоры с принудительной циркуляционной смазкой",
                "installation_date": "2021-06-10",
                "age_months": 41,
                "criticality_factor": 1.7,
            },
        ],
    },
]


def update_database(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()

    for eq in EQUIPMENT_DATA:
        comps_json = json.dumps(eq["components"], ensure_ascii=False)
        all_ids = [eq["id"]] + eq.get("aliases", [])
        
        for curr_id in all_ids:
            cursor.execute(
                """
                INSERT INTO equipment (
                    id, name, serial_number, location, installation_date,
                    component_age, last_maintenance_date, status, components_json,
                    created_at, updated_at, inspection_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    serial_number = excluded.serial_number,
                    location = excluded.location,
                    installation_date = excluded.installation_date,
                    component_age = excluded.component_age,
                    last_maintenance_date = excluded.last_maintenance_date,
                    status = excluded.status,
                    components_json = excluded.components_json,
                    updated_at = excluded.updated_at
                """,
                (
                    curr_id,
                    eq["name"],
                    eq["serial_number"],
                    eq["location"],
                    eq["installation_date"],
                    eq["component_age"],
                    eq["last_maintenance_date"],
                    eq["status"],
                    comps_json,
                    now_str,
                    now_str,
                ),
            )
            print(f"  [DB] Saved aggregate: {curr_id} ({eq['name']})")

    conn.commit()
    conn.close()


def generate_qr_card(eq: dict, output_dir: Path, static_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    # 1. Plain QR code for machine reading
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=3,
    )
    qr.add_data(eq["id"])
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#135aa6", back_color="white").convert("RGB")

    raw_qr_path = output_dir / f"{eq['id']}_qr_raw.png"
    qr_img.save(raw_qr_path)

    # 2. Branded printable card with label and specifications
    card_w, card_h = 700, 850
    card = Image.new("RGB", (card_w, card_h), "#ffffff")
    draw = ImageDraw.Draw(card)

    # Fonts
    font_path = "C:/Windows/Fonts/arial.ttf"
    bold_path = "C:/Windows/Fonts/arialbd.ttf"
    try:
        f_brand = ImageFont.truetype(bold_path, 22)
        f_title = ImageFont.truetype(bold_path, 20)
        f_id = ImageFont.truetype(bold_path, 24)
        f_meta = ImageFont.truetype(font_path, 16)
        f_small = ImageFont.truetype(font_path, 14)
    except Exception:
        f_brand = f_title = f_id = f_meta = f_small = ImageFont.load_default()

    # Outer border & header
    draw.rectangle([(10, 10), (card_w - 10, card_h - 10)], outline="#135aa6", width=3)
    draw.rectangle([(10, 10), (card_w - 10, 65)], fill="#135aa6")
    draw.text((30, 24), "ПРОМСКАН · КСТ ЭНЕРГО", fill="#ffffff", font=f_brand)
    draw.text((card_w - 190, 27), "СИСТЕМА ТОиР", fill="#ffffff", font=f_small)

    # Center QR code
    qr_size = 360
    qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_x = (card_w - qr_size) // 2
    qr_y = 85
    card.paste(qr_resized, (qr_x, qr_y))

    # ID Badge
    draw.rectangle([(40, 465), (card_w - 40, 520)], fill="#f4f5f8", outline="#d5d9de", width=1)
    draw.text((60, 478), f"ID: {eq['id']}", fill="#135aa6", font=f_id)

    # Equipment name & details
    y = 540
    # Wrap equipment name
    name_lines = []
    words = eq["name"].split()
    line = ""
    for w in words:
        if len(line + " " + w) < 45:
            line = (line + " " + w).strip()
        else:
            name_lines.append(line)
            line = w
    if line:
        name_lines.append(line)

    for nl in name_lines:
        draw.text((45, y), nl, fill="#313132", font=f_title)
        y += 28

    y += 10
    draw.text((45, y), f"Зав. №: {eq['serial_number']}", fill="#5a5e67", font=f_meta)
    y += 24
    draw.text((45, y), f"Установка: {eq['location']}", fill="#5a5e67", font=f_meta)
    y += 24
    draw.text((45, y), f"Ввод: {eq['installation_date']} ({eq['component_age']})", fill="#5a5e67", font=f_meta)
    y += 24
    draw.text((45, y), f"Узлов в составе: {len(eq['components'])} шт. · Статус: {eq['status'].upper()}", fill="#2a6f3e", font=f_meta)

    # Footer instructions
    draw.rectangle([(20, card_h - 60), (card_w - 20, card_h - 20)], fill="#eef0f5")
    draw.text((35, card_h - 48), "Наведите камеру мобильного приложения или сканера для осмотра", fill="#42444a", font=f_small)

    card_path = output_dir / f"{eq['id']}_card.png"
    card.save(card_path)

    # Copy to static/qr for web viewing
    card.save(static_dir / f"{eq['id']}.png")
    qr_img.save(static_dir / f"{eq['id']}_qr.png")

    print(f"  [QR] Generated card & QR: {card_path}")
    return card_path


def create_html_catalog(equipments: list, output_file: Path):
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Каталог QR-кодов оборудования — ПромСкан</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f5f8; margin: 0; padding: 24px; color: #313132; }
  h1 { color: #135aa6; margin-bottom: 8px; }
  .subtitle { color: #5a5e67; margin-top: 0; margin-bottom: 24px; }
  .print-btn { background: #135aa6; color: white; border: none; padding: 12px 24px; font-size: 15px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-bottom: 24px; }
  .print-btn:hover { background: #0f4a89; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; }
  .card { background: white; border: 1px solid #d5d9de; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); page-break-inside: avoid; }
  .card-header { font-weight: bold; font-size: 17px; color: #135aa6; margin-bottom: 6px; }
  .qr-box { text-align: center; margin: 16px 0; background: #fdfdfd; padding: 12px; border: 1px dashed #c0c6cf; border-radius: 8px; }
  .qr-box img { max-width: 200px; height: auto; }
  .badge { display: inline-block; background: #eef0f5; padding: 4px 10px; font-family: monospace; font-size: 13px; font-weight: bold; border-radius: 6px; color: #135aa6; margin-bottom: 12px; }
  .meta { font-size: 13px; color: #5a5e67; line-height: 1.6; }
  .components { margin-top: 12px; font-size: 12px; border-top: 1px solid #e5e7ea; padding-top: 8px; }
  .comp-item { margin-bottom: 4px; color: #42444a; }
  @media print {
    body { background: white; padding: 0; }
    .print-btn { display: none; }
    .grid { display: block; }
    .card { page-break-after: always; margin-bottom: 20px; border: 2px solid #135aa6; }
  }
</style>
</head>
<body>
<h1>Каталог QR-кодов агрегатов КСТ Энерго</h1>
<p class="subtitle">Используйте для печати шильдиков или сканирования камерой приложения ПромСкан прямо с экрана.</p>
<button class="print-btn" onclick="window.print()">Распечатать все шильдики</button>
<div class="grid">
"""
    for eq in equipments:
        comps_html = "".join([f"<div class='comp-item'>• {c['name']}</div>" for c in eq["components"]])
        html += f"""
  <div class="card">
    <div class="card-header">{eq['name']}</div>
    <div class="badge">ID: {eq['id']}</div>
    <div class="qr-box">
      <img src="{eq['id']}_qr_raw.png" alt="QR {eq['id']}">
      <div style="font-size: 11px; color: #5a5e67; margin-top: 4px;">Код для сканирования: {eq['id']}</div>
    </div>
    <div class="meta">
      <div><b>Заводской номер:</b> {eq['serial_number']}</div>
      <div><b>Установка:</b> {eq['location']}</div>
      <div><b>Ввод в работу:</b> {eq['installation_date']} ({eq['component_age']})</div>
      <div><b>Последнее ТО:</b> {eq['last_maintenance_date']}</div>
    </div>
    <div class="components">
      <b>Узлы в составе агрегата ({len(eq['components'])}):</b>
      {comps_html}
    </div>
  </div>
"""

    html += """
</div>
</body>
</html>
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [HTML] Created printable catalog: {output_file}")


def main():
    root_dir = Path(__file__).resolve().parent.parent
    db_path = root_dir / "data" / "toir.db"
    desktop_qr_dir = Path(r"c:\Users\ardor\Desktop\Новая папка\QR_коды")
    static_qr_dir = root_dir / "static" / "qr"

    print("=== 1. Updating SQLite Database ===")
    update_database(db_path)

    print("\n=== 2. Generating QR Codes and Branded Cards ===")
    for eq in EQUIPMENT_DATA:
        generate_qr_card(eq, desktop_qr_dir, static_qr_dir)

    print("\n=== 3. Creating HTML Printable Catalog ===")
    create_html_catalog(EQUIPMENT_DATA, desktop_qr_dir / "Каталог_QR_кодов.html")
    create_html_catalog(EQUIPMENT_DATA, static_qr_dir / "index.html")

    print("\n=== Done! All equipment and QR codes successfully created. ===")


if __name__ == "__main__":
    main()
