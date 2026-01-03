import requests
from bs4 import BeautifulSoup
import json
import re
import os
from typing import Dict, Any, List
from datetime import datetime
import statistics

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich import box
    from rich.json import JSON
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console()

from wind_analysis_tool import *

# =============================================================================
# YARDIMCI FONKSİYONLAR VE SABITLER
# =============================================================================

yon_haritasi = {
    "K": "Kuzey",
    "G": "Güney",
    "D": "Doğu",
    "B": "Batı",
    "KD": "Kuzeydoğu",
    "KB": "Kuzeybatı",
    "GD": "Güneydoğu",
    "GB": "Güneybatı"
}

# Temel klasör yapısı
BASE_DIR = "www"
SVG_DIR = os.path.join(BASE_DIR, "svg")


def ensure_directory_structure():
    """
    Gerekli klasör yapısını oluşturur.
    - www/
    - www/svg/
    """
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(SVG_DIR, exist_ok=True)
    print(f"✓ Klasör yapısı hazır: {BASE_DIR}/, {SVG_DIR}/")


def extract_day_index_from_url(url: str) -> str:
    """
    URL'den gün indeksini çıkarır (/0/, /1/, /2/ gibi)
    
    Örnek:
        'https://havadurumu15gunluk.xyz/saat-saat-havadurumu/0/293/...' -> '0'
        'https://havadurumu15gunluk.xyz/saat-saat-havadurumu/1/293/...' -> '1'
    
    Args:
        url: Saatlik hava durumu URL'si
    
    Returns:
        Gün indeksi (string) veya 'unknown'
    """
    match = re.search(r'/saat-saat-havadurumu/(\d+)/', url)
    return match.group(1) if match else 'unknown'


def create_day_directory(day_index: str) -> str:
    """
    Belirtilen gün indeksi için klasör oluşturur.
    
    Args:
        day_index: Gün indeksi (0, 1, 2...)
    
    Returns:
        Oluşturulan klasör yolu
    """
    day_dir = os.path.join(BASE_DIR, day_index)
    os.makedirs(day_dir, exist_ok=True)
    return day_dir


# =============================================================================
# 7 GÜNLÜK HAVA DURUMU FONKSİYONU
# =============================================================================

def get7DaysWeatherData(city: str, verbose: bool = False, svg_save: str = None, 
                        output_format: str = "JSON") -> str:
    """
    7 günlük hava durumu verilerini çeker ve belirtilen formatta döndürür.
    
    Args:
        city: Şehir adı
        verbose: Rich çıktı gösterilsin mi?
        svg_save: SVG dosya adı (www/svg/ altına kaydedilir)
        output_format: Çıktı formatı ("JSON", "HTML", "TXT")
    
    Returns:
        JSON string (status, city, format, content, saved_file bilgileriyle)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    search_url = f"https://havadurumu15gunluk.xyz/backend-search.php?term={city}"
    
    try:
        # Şehir araması
        res = requests.get(search_url, headers=headers, timeout=15)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, 'html.parser')
        a_tag = soup.find('a')
        
        if not a_tag:
            return json.dumps({"status": "error", "message": "Şehir bulunamadı."}, ensure_ascii=False)
            
        # URL dönüşümü (15 günlük -> 7 günlük)
        original_url = a_tag['href']
        target_url = original_url.replace("15-gunluk", "7-gunluk")
        
        # Sayfa çekme
        page_res = requests.get(target_url, headers=headers, timeout=15)
        page_res.raise_for_status()
        
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        table = page_soup.find('table')
        
        if not table:
            return json.dumps({"status": "error", "message": "Tablo bulunamadı."}, ensure_ascii=False)
            
        # Veri çekme
        weather_data = []
        rows = table.find_all('tr')[1:]  # Başlık satırını atla
        base_domain = "https://havadurumu15gunluk.xyz"

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            
            # Durum ve detay linki
            durum_cell = cols[1]
            durum_link_tag = durum_cell.find('a')
            durum_text = durum_cell.get_text(" ", strip=True).replace("Saatlik", "").strip()
            
            # Detay linki oluştur
            saatlik_link = None
            if durum_link_tag and 'href' in durum_link_tag.attrs:
                href = durum_link_tag['href']
                saatlik_link = href if href.startswith("http") else f"{base_domain}/{href.lstrip('/')}"

            # Yağış oranı
            yagis_icon = cols[2].find('i')
            yagis_oran = f"%{yagis_icon['title']}" if yagis_icon and yagis_icon.has_attr('title') else "%0"
            
            weather_data.append({
                "tarih": cols[0].get_text(strip=True),
                "durum": durum_text,
                "detay_link": saatlik_link,
                "yagis": yagis_oran,
                "gunduz": cols[3].get_text(strip=True),
                "gece": cols[4].get_text(strip=True)
            })
        
        # --- RICH & SVG İŞLEMLERİ ---
        saved_svg_path = None
        if verbose or svg_save:
            console_obj = Console(record=True) if svg_save else Console()
            rich_table = Table(title=f"{city.capitalize()} 7 Günlük Hava Durumu")
            rich_table.add_column("Tarih", style="cyan")
            rich_table.add_column("Hava Durumu", style="magenta")
            rich_table.add_column("Yağış", justify="center", style="green")
            rich_table.add_column("Gündüz", justify="right", style="yellow")
            rich_table.add_column("Gece", justify="right", style="blue")
            
            for day in weather_data:
                rich_table.add_row(day["tarih"], day["durum"], day["yagis"], day["gunduz"], day["gece"])
            
            if verbose:
                console_obj.print(rich_table)
            
            if svg_save:
                ensure_directory_structure()
                if not svg_save.endswith(".svg"):
                    svg_save += ".svg"
                svg_path = os.path.join(SVG_DIR, svg_save)
                console_obj.save_svg(svg_path, title=f"{city.capitalize()} Hava Durumu")
                saved_svg_path = os.path.abspath(svg_path)
                print(f"✓ SVG kaydedildi: {saved_svg_path}")

        # --- FORMATLAMA İŞLEMLERİ ---
        result_content = None

        if output_format == "HTML":
            result_content = _generate_weekly_html(weather_data, city)
        
        elif output_format == "TXT":
            result_content = _generate_weekly_txt(weather_data)
        
        else:  # JSON
            result_content = weather_data

        output = {
            "status": "success",
            "city": city,
            "format": output_format,
            "saved_file": saved_svg_path,
            "content": result_content
        }
        
        return json.dumps(output, ensure_ascii=False, indent=4)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


def _generate_weekly_html(weather_data: List[Dict], city: str) -> str:
    """7 günlük hava durumu için HTML oluşturur (Detay linkleri ile)"""
    
    rows_list = []
    for d in weather_data:
        # Detay linkini belirle
        if d.get("detay_link"):
            day_index = extract_day_index_from_url(d["detay_link"])
            # Tarih hücresini link yap
            tarih_html = f'<a href="./{day_index}/saatlik.html" style="color: #2c3e50; text-decoration: none; font-weight: 600;">{d["tarih"]} 📊</a>'
        else:
            tarih_html = d["tarih"]
        
        row_html = "<tr><td>{}</td><td>{}</td><td style='text-align:center;'>{}</td><td style='text-align:center;'>{}</td><td style='text-align:center;'>{}</td></tr>".format(
            tarih_html, d['durum'], d['yagis'], d['gunduz'], d['gece']
        )
        rows_list.append(row_html)
    
    html = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{} - 7 Günlük Hava Durumu</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 40px auto;
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .subtitle {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 40px;
            font-size: 1.1em;
        }}
        .info-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
            font-size: 1.1em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
            border-radius: 10px;
            overflow: hidden;
        }}
        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        th {{
            padding: 18px;
            text-align: left;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.9em;
        }}
        td {{
            padding: 16px 18px;
            border-bottom: 1px solid #ecf0f1;
            color: #2c3e50;
        }}
        tbody tr {{ transition: all 0.3s ease; }}
        tbody tr:hover {{
            background: #f8f9fa;
            transform: scale(1.02);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}
        tbody tr:last-child td {{ border-bottom: none; }}
        td a {{
            color: #2c3e50;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            display: block;
        }}
        td a:hover {{
            color: #667eea;
            transform: translateX(5px);
        }}
        .badge {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 5px;
        }}
        @media (max-width: 768px) {{
            .container {{ padding: 20px; }}
            h1 {{ font-size: 1.8em; }}
            th, td {{ padding: 10px; font-size: 0.9em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌤️ {} - Hava Durumu</h1>
        <p class="subtitle">7 Günlük Detaylı Tahmin</p>
        
        <div class="info-box">
            💡 <strong>Tarih</strong> üzerine tıklayarak saatlik detaylara ulaşabilirsiniz
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>📅 Tarih</th>
                    <th>☁️ Hava Durumu</th>
                    <th style="text-align:center;">💧 Yağış</th>
                    <th style="text-align:center;">🌞 Gündüz</th>
                    <th style="text-align:center;">🌙 Gece</th>
                </tr>
            </thead>
            <tbody>
                {}
            </tbody>
        </table>
    </div>
</body>
</html>
    """.format(city.capitalize(), city.capitalize(), "".join(rows_list))
    
    return html


def _generate_weekly_txt(weather_data: List[Dict]) -> str:
    """7 günlük hava durumu için TXT formatı"""
    header = f"{'Tarih':<12} | {'Durum':<20} | {'Yağış':<6} | {'Gnd':<5} | {'Gce':<5}\n"
    sep = "-" * len(header) + "\n"
    rows_txt = "".join([
        f"{d['tarih']:<12} | {d['durum']:<20} | {d['yagis']:<6} | {d['gunduz']:<5} | {d['gece']:<5}\n"
        for d in weather_data
    ])
    return header + sep + rows_txt


# =============================================================================
# SAATLİK HAVA DURUMU FONKSİYONU
# =============================================================================

def getData(url: str, verbose: bool = False, output_format: str = None, 
            save_svg: str = None) -> Any:
    """
    URL'den saatlik hava durumu verilerini çeker.
    
    Args:
        url: Hava durumu sayfasının URL'si
        verbose: Rich ile detaylı çıktı göster
        output_format: Çıktı formatı ("HTML", "TXT" veya None)
        save_svg: SVG dosya adı (www/svg/ altına kaydedilir)
    
    Returns:
        output_format belirtilmişse dict (status, content vb.),
        aksi halde direkt weather_data listesi
    """
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    try:
        # Sayfayı çek (cache bypass için session kullanma)
        print(f"    → Çekiliyor: {url}")
        time.sleep(1)  # Rate limiting
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # DEBUG: HTML'in ilk 500 karakterini göster
        print(f"    → HTML uzunluğu: {len(response.text)} karakter")
        print(f"    → İlk tarih bilgisi: {response.text[response.text.find('title='):response.text.find('title=')+50] if 'title=' in response.text else 'bulunamadı'}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table')
        
        if not tables:
            if output_format:
                return {"status": "error", "message": "Tablo bulunamadı", "content": None}
            return []
        
        # URL'den gün indeksini çıkar ve doğru table'ı seç
        day_index = extract_day_index_from_url(url)
        try:
            table_index = int(day_index) if day_index != 'unknown' else 0
        except:
            table_index = 0
        
        # Eğer o indekste table yoksa son table'ı kullan
        if table_index >= len(tables):
            table_index = len(tables) - 1
        
        target_table = tables[table_index]
        print(f"    → Toplam {len(tables)} table var, {table_index}. table kullanılıyor")
        
        rows = target_table.find_all('tr')
        
        print(f"    → Tablo bulundu: {len(rows)-1} satır")
        
        weather_data = []
        
        # Veri çekme
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 6:
                continue
            
            # Saat bilgisi
            saat_raw = cols[0].text.strip()
            saat_parca, dakika_parca = saat_raw.split(':')
            
            # Rüzgar bilgisi
            ruzgar_raw = cols[5].text.strip()
            yon_match = re.search(r'([A-ZÇĞİÖŞÜ]+)', ruzgar_raw)
            yon_abb = yon_match.group(1) if yon_match else "Bilinmiyor"
            yon = yon_haritasi.get(yon_abb, "Bilinmeyen")
            hiz_match = re.search(r'(\d+)', ruzgar_raw)
            hiz = int(hiz_match.group(1)) if hiz_match else 0

            entry = {
                "tarih": row.get('title', 'Bilinmiyor'),
                "zaman": {
                    "tam": saat_raw,
                    "saat": int(saat_parca),
                    "dakika": int(dakika_parca)
                },
                "durum": cols[1].find('span').text.strip() if cols[1].find('span') else cols[1].text.strip(),
                "sicaklik": int(re.search(r'(\d+)', cols[2].text).group(1)),
                "hissedilen": int(re.search(r'(\d+)', cols[3].text).group(1)),
                "ruzgar": {
                    "yon": yon,
                    "hiz": hiz
                },
                "_debug_url": url  # DEBUG için URL ekle
            }
            weather_data.append(entry)
        
        # DEBUG: İlk ve son kayıt
        if weather_data:
            print(f"    → İlk kayıt tarihi: {weather_data[0]['tarih']}")
            print(f"    → Son kayıt tarihi: {weather_data[-1]['tarih']}")

        # --- RICH & SVG İŞLEMLERİ ---
        saved_svg_path = None
        if verbose or save_svg:
            console_obj = Console(record=True) if save_svg else Console()
            
            rich_table = Table(title="☁️ Saatlik Hava Durumu Detayı")
            rich_table.add_column("Saat", style="cyan", justify="center")
            rich_table.add_column("Durum", style="magenta")
            rich_table.add_column("Sıcaklık", justify="center", style="yellow")
            rich_table.add_column("Hissedilen", justify="center", style="red")
            rich_table.add_column("Rüzgar", justify="center", style="blue")
            
            for entry in weather_data:
                rich_table.add_row(
                    entry['zaman']['tam'],
                    entry['durum'],
                    f"{entry['sicaklik']}°C",
                    f"{entry['hissedilen']}°C",
                    f"{entry['ruzgar']['yon']} {entry['ruzgar']['hiz']} km/h"
                )
            
            if verbose:
                console_obj.print(Panel.fit(
                    f"[bold green]✓ Veri çekme başarılı![/bold green]\n"
                    f"[dim]Toplam {len(weather_data)} saatlik veri alındı[/dim]",
                    border_style="green"
                ))
                console_obj.print(rich_table)
            
            if save_svg:
                ensure_directory_structure()
                if not save_svg.endswith(".svg"):
                    save_svg += ".svg"
                svg_path = os.path.join(SVG_DIR, save_svg)
                console_obj.save_svg(svg_path, title="Saatlik Hava Durumu")
                saved_svg_path = os.path.abspath(svg_path)
                print(f"✓ SVG kaydedildi: {saved_svg_path}")

        # --- OUTPUT FORMAT İŞLEME ---
        if output_format:
            output_format = output_format.upper()
            result_content = None
            
            if output_format == "HTML":
                result_content = _generate_hourly_html(weather_data, url)
            
            elif output_format == "TXT":
                result_content = _generate_hourly_txt(weather_data)
            
            else:  # JSON
                result_content = weather_data
            
            return {
                "status": "success",
                "format": output_format,
                "data_count": len(weather_data),
                "saved_svg": saved_svg_path,
                "url": url,
                "content": result_content
            }
        
        # Format belirtilmemişse direkt liste döndür
        return weather_data

    except Exception as e:
        if verbose:
            console.print(f"[bold red]Hata Oluştu:[/bold red] {str(e)}")
        
        if output_format:
            return {"status": "error", "message": str(e), "content": None}
        return []


def _generate_hourly_html(weather_data: List[Dict], source_url: str = "") -> str:
    """Saatlik hava durumu için HTML oluşturur"""
    
    rows_html = []
    for entry in weather_data:
        row = """
        <tr>
            <td style="text-align:center;">{}</td>
            <td>{}</td>
            <td style="text-align:center;">{}</td>
            <td style="text-align:center;">{}</td>
            <td style="text-align:center;">{}</td>
            <td style="text-align:center;">{} km/h</td>
        </tr>
        """.format(
            entry['zaman']['tam'],
            entry['durum'],
            f"{entry['sicaklik']}°C",
            f"{entry['hissedilen']}°C",
            entry['ruzgar']['yon'],
            entry['ruzgar']['hiz']
        )
        rows_html.append(row)
    
    html = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Saatlik Hava Durumu</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .buttons {{
            position: fixed;
            top: 20px;
            left: 20px;
            display: inline-flex;
            z-index: 1000;
        }}
        .back-link {{
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            color: white;
            padding: 12px 20px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            border: 1px solid rgba(255, 255, 255, 0.3);
            transition: all 0.3s ease;
            margin: 0 5px;
        }}
        .back-link:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateX(-5px);
        }}
        .container {{
            max-width: 1400px;
            margin: 80px auto 20px;
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .subtitle {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 40px;
            font-size: 1.1em;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 15px;
            text-align: center;
            min-width: 150px;
            margin: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }}
        .stat-card h3 {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .stat-card p {{
            font-size: 1.8em;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
            border-radius: 10px;
            overflow: hidden;
        }}
        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        th {{
            padding: 18px;
            text-align: left;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.9em;
        }}
        td {{
            padding: 16px 18px;
            border-bottom: 1px solid #ecf0f1;
            color: #2c3e50;
        }}
        tbody tr {{ transition: all 0.3s ease; }}
        tbody tr:hover {{
            background: #f8f9fa;
            transform: scale(1.01);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}
        tbody tr:last-child td {{ border-bottom: none; }}
        @media (max-width: 768px) {{
            .container {{ padding: 20px; margin-top: 60px; }}
            h1 {{ font-size: 1.8em; }}
            th, td {{ padding: 10px; font-size: 0.9em; }}
            .stats {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="buttons">
        <a href="../haftalik.html" class="back-link">← Haftalık</a>
        <a href="ruzgar_rapor.html" class="back-link">Rüzgar Detayları</a>
    </div>
    
    <div class="container">
        <h1>⏰ Saatlik Hava Durumu</h1>
        <p class="subtitle">Detaylı Saatlik Tahmin - {} Veri Noktası</p>
        
        <div class="stats">
            <div class="stat-card">
                <h3>📊 Toplam Veri</h3>
                <p>{}</p>
            </div>
            <div class="stat-card">
                <h3>🕐 İlk Saat</h3>
                <p>{}</p>
            </div>
            <div class="stat-card">
                <h3>🕐 Son Saat</h3>
                <p>{}</p>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th style="text-align:center;">🕐 Saat</th>
                    <th>☁️ Hava Durumu</th>
                    <th style="text-align:center;">🌡️ Sıcaklık</th>
                    <th style="text-align:center;">🤒 Hissedilen</th>
                    <th style="text-align:center;">🧭 Yön</th>
                    <th style="text-align:center;">💨 Hız</th>
                </tr>
            </thead>
            <tbody>
                {}
            </tbody>
        </table>
    </div>
</body>
</html>
    """.format(
        len(weather_data),
        len(weather_data),
        weather_data[0]['zaman']['tam'] if weather_data else "N/A",
        weather_data[-1]['zaman']['tam'] if weather_data else "N/A",
        "".join(rows_html)
    )
    
    return html


def _generate_hourly_txt(weather_data: List[Dict]) -> str:
    """Saatlik hava durumu için TXT formatı"""
    txt = f"""
{'='*80}
                    SAATLİK HAVA DURUMU RAPORU
{'='*80}

Toplam Veri: {len(weather_data)} saat
İlk Saat: {weather_data[0]['zaman']['tam'] if weather_data else 'N/A'}
Son Saat: {weather_data[-1]['zaman']['tam'] if weather_data else 'N/A'}

{'-'*80}
{'Saat':^8} | {'Durum':<20} | {'Sıc':>5} | {'His':>5} | {'Yön':<10} | {'Hız':>6}
{'-'*80}
"""
    
    for entry in weather_data:
        txt += "{:^8} | {:<20} | {:>5} | {:>5} | {:<10} | {:>6}\n".format(
            entry['zaman']['tam'],
            entry['durum'][:20],
            f"{entry['sicaklik']}°C",
            f"{entry['hissedilen']}°C",
            entry['ruzgar']['yon'][:10],
            f"{entry['ruzgar']['hiz']} km/h"
        )
    
    txt += "=" * 80 + "\n"
    return txt


# =============================================================================
# DOSYA KAYIT FONKSİYONLARI
# =============================================================================

def save_weekly_report(city: str) -> Dict[str, Any]:
    """
    7 günlük hava durumunu HTML olarak www/haftalik.html'e kaydeder.
    
    Returns:
        Kayıt bilgilerini içeren dict
    """
    ensure_directory_structure()
    
    # Önce JSON formatında alalım (ham veri için)
    result_json_raw = get7DaysWeatherData(city, output_format="JSON", svg_save=f"{city}_weekly")
    result_raw = json.loads(result_json_raw)
    
    if result_raw["status"] != "success":
        return result_raw
    
    # Şimdi HTML formatında alalım (kayıt için)
    result_json_html = get7DaysWeatherData(city, output_format="HTML", svg_save=None)
    result_html = json.loads(result_json_html)
    
    if result_html["status"] != "success":
        return result_html
    
    # HTML'i kaydet
    weekly_path = os.path.join(BASE_DIR, "haftalik.html")
    with open(weekly_path, "w", encoding="utf-8") as f:
        f.write(result_html["content"])
    
    print(f"✓ Haftalık rapor kaydedildi: {os.path.abspath(weekly_path)}")
    
    return {
        "status": "success",
        "file_path": os.path.abspath(weekly_path),
        "city": city,
        "weather_data": result_raw["content"]  # JSON formatındaki ham veriyi döndür
    }


def save_hourly_reports(weather_data_list: List[Dict]) -> Dict[str, List[str]]:
    """
    7 günlük veriden detay linklerini çeker ve her birini ilgili klasöre kaydeder.
    
    Args:
        weather_data_list: get7DaysWeatherData'dan dönen content listesi
    
    Returns:
        Kaydedilen dosyaların bilgilerini içeren dict
    """
    ensure_directory_structure()
    saved_files = []
    
    for item in weather_data_list:
        detail_url = item.get("detay_link")
        
        if not detail_url:
            continue
        
        # URL'den gün indeksini çıkar (0, 1, 2...)
        day_index = extract_day_index_from_url(detail_url)
        
        # İlgili gün klasörünü oluştur
        day_dir = create_day_directory(day_index)
        
        print(f"\n🔄 {item['tarih']} işleniyor (URL: {detail_url})")
        
        # Önce ham veriyi çek
        raw_data = getData(detail_url, verbose=False)
        
        if not raw_data or len(raw_data) == 0:
            print(f"⚠ {item['tarih']} için ham veri çekilemedi!")
            continue
        
        print(f"  ✓ Ham veri çekildi: {len(raw_data)} kayıt")
        
        # Ham veriden HTML oluştur
        html_content = _generate_hourly_html(raw_data, detail_url)
        
        # HTML dosyasını kaydet
        html_path = os.path.join(day_dir, "saatlik.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        saved_files.append({
            "day": item['tarih'],
            "day_index": day_index,
            "path": os.path.abspath(html_path),
            "url": detail_url
        })
        wind_report = windanalysis(raw_data, verbose=False, output_format="HTML")
        wind_path = os.path.join(day_dir, "ruzgar_rapor.html")
        with open(wind_path, "w", encoding="utf-8") as f:
            f.write(wind_report["content"])
        
        print(f"  ✓ Rüzgar raporu kaydedildi")
        print(f"  ✓ {item['tarih']} tamamlandı → {day_dir}/")
    
    return {
        "status": "success",
        "saved_files": saved_files,
        "total_saved": len(saved_files)
    }


# =============================================================================
# ANA ÇALIŞTIRMA FONKSİYONU
# =============================================================================

def generate_all_reports(city: str = "Bursa") -> None:
    """
    Tüm raporları oluşturur ve klasör yapısına kaydeder.
    
    Klasör yapısı:
        www/
        ├── haftalik.html           (7 günlük özet)
        ├── svg/                    (SVG dosyaları)
        │   ├── bursa_weekly.svg
        │   ├── hourly_day0.svg
        │   └── hourly_day1.svg
        ├── 0/                      (Bugün)
        │   ├── saatlik.html
        │   └── ruzgar_rapor.html
        ├── 1/                      (Yarın)
        │   ├── saatlik.html
        │   └── ruzgar_rapor.html
        └── ...
    """
    print("="*80)
    print(f"🌤️  {city.upper()} HAVA DURUMU RAPORU OLUŞTURULUYOR")
    print("="*80)
    
    # 1. Haftalık raporu kaydet
    print("\n📅 1/3: Haftalık rapor oluşturuluyor...")
    weekly_result = save_weekly_report(city)
    
    if weekly_result["status"] != "success":
        print(f"❌ Haftalık rapor oluşturulamadı: {weekly_result.get('message', 'Bilinmeyen hata')}")
        return
    
    # 2. Saatlik raporları kaydet
    print("\n⏰ 2/3: Saatlik raporlar oluşturuluyor...")
    
    # weather_data artık doğrudan liste olmalı
    weather_data = weekly_result["weather_data"]
    
    hourly_result = save_hourly_reports(weather_data)
    
    # 3. Özet bilgi
    print("\n" + "="*80)
    print("✅ TÜM RAPORLAR OLUŞTURULDU!")
    print("="*80)
    print(f"📁 Ana klasör: {os.path.abspath(BASE_DIR)}")
    print(f"📄 Haftalık rapor: haftalik.html")
    print(f"📊 Saatlik rapor sayısı: {hourly_result['total_saved']}")
    print(f"🖼️  SVG dosyaları: {SVG_DIR}/")
    print("\nKaydedilen günler:")
    for file_info in hourly_result['saved_files']:
        print(f"  • {file_info['day']} → {BASE_DIR}/{file_info['day_index']}/")
    print("="*80)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Tüm raporları oluştur
    generate_all_reports("Bursa")
    
    # Manuel test için örnekler:
    # get7DaysWeatherData("Bursa", verbose=True, svg_save="test_weekly", output_format="JSON")
    # getData("URL_BURAYA", verbose=True, output_format="HTML", save_svg="test_hourly")
