import statistics
from datetime import datetime
from typing import List, Dict, Any
import json

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# === DURUM KODLARI ===
DURUM_KODLARI = {
    "NORMAL": {
        "kod": 0,
        "aciklama": "Normal rüzgar koşulları",
        "renk": "green"
    },
    "DUSUK_RUZGAR": {
        "kod": 1,
        "aciklama": "Ortalamanın altında rüzgar",
        "renk": "blue"
    },
    "YUKSEK_RUZGAR": {
        "kod": 2,
        "aciklama": "Ortalamanın üstünde rüzgar",
        "renk": "yellow"
    },
    "ANOMALI_YUKSEK": {
        "kod": 3,
        "aciklama": "Yüksek rüzgar anomalisi",
        "renk": "red"
    },
    "ANOMALI_DUSUK": {
        "kod": 4,
        "aciklama": "Düşük rüzgar anomalisi",
        "renk": "cyan"
    },
    "ISTIKRARSIZ": {
        "kod": 5,
        "aciklama": "İstikrarsız rüzgar paterni",
        "renk": "magenta"
    },
    "TREND_ARTIS": {
        "kod": 10,
        "aciklama": "Rüzgar hızı artış trendinde",
        "renk": "bright_yellow"
    },
    "TREND_AZALIS": {
        "kod": 11,
        "aciklama": "Rüzgar hızı azalış trendinde",
        "renk": "bright_blue"
    },
    "TREND_SABIT": {
        "kod": 12,
        "aciklama": "Rüzgar hızı stabil",
        "renk": "bright_green"
    }
}

def windanalysis(data: List[Dict[str, Any]], verbose: bool = False, output_format: str = None, save_svg: str = None) -> Dict[str, Any]:
    """
    Meteorolojik rüzgar analiz modülü.
    
    Args:
        data: Hava durumu verisi (getData fonksiyonundan alınan)
        verbose: True ise Rich ile detaylı çıktı gösterir
        output_format: Çıktı formatı ("HTML", "TXT" veya None)
        save_svg: SVG dosya adı (Rich console'un SVG export özelliği kullanılır)
    
    Returns:
        Analiz raporu (dict)
    """
    
    if not data or len(data) == 0:
        return {
            "hata": "Veri bulunamadı",
            "durum_kodu": -1,
            "durum": "BAŞARISIZ"
        }
    
    console = Console(record=True) if RICH_AVAILABLE and (verbose or save_svg) else None
    
    if verbose and console:
        console.print(Panel.fit(
            "[bold cyan]🌪️  RÜZGAR ANALİZ MODÜLÜ[/bold cyan]\n"
            f"[dim]Analiz başlatılıyor... {len(data)} veri noktası[/dim]",
            border_style="cyan"
        ))
    
    # === VERİ TOPLAMA ===
    ruzgar_hizlari = []
    ruzgar_yonleri = []
    sicakliklar = []
    zaman_damgalari = []
    
    for entry in data:
        ruzgar_hizlari.append(entry['ruzgar']['hiz'])
        ruzgar_yonleri.append(entry['ruzgar']['yon'])
        sicakliklar.append(entry['sicaklik'])
        zaman_damgalari.append(entry['zaman']['tam'])
    
    # === İSTATİSTİKSEL HESAPLAMALAR ===
    ortalama_hiz = statistics.mean(ruzgar_hizlari)
    medyan_hiz = statistics.median(ruzgar_hizlari)
    min_hiz = min(ruzgar_hizlari)
    max_hiz = max(ruzgar_hizlari)
    std_sapma = statistics.stdev(ruzgar_hizlari) if len(ruzgar_hizlari) > 1 else 0
    
    if verbose and console:
        stat_table = Table(title="📊 İstatistiksel Özet", box=box.ROUNDED)
        stat_table.add_column("Metrik", style="cyan")
        stat_table.add_column("Değer", style="yellow", justify="right")
        stat_table.add_row("Ortalama Hız", f"{ortalama_hiz:.2f} km/h")
        stat_table.add_row("Medyan Hız", f"{medyan_hiz:.2f} km/h")
        stat_table.add_row("Min Hız", f"{min_hiz} km/h")
        stat_table.add_row("Max Hız", f"{max_hiz} km/h")
        stat_table.add_row("Std Sapma", f"{std_sapma:.2f}")
        console.print(stat_table)
    
    # === ANOMALI TESPİT PARAMETRELERİ ===
    ust_esik = ortalama_hiz + (1.5 * std_sapma)
    alt_esik = max(0, ortalama_hiz - (1.5 * std_sapma))
    
    # === GENEL DURUM KODU BELİRLEME ===
    volatilite_orani = (std_sapma / ortalama_hiz) * 100 if ortalama_hiz > 0 else 0
    
    if volatilite_orani > 30:
        genel_durum = "ISTIKRARSIZ"
    elif max_hiz > ust_esik:
        genel_durum = "YUKSEK_RUZGAR"
    elif min_hiz < alt_esik:
        genel_durum = "DUSUK_RUZGAR"
    else:
        genel_durum = "NORMAL"
    
    # === ANOMALI ANALİZİ ===
    anomaliler = []
    for i, hiz in enumerate(ruzgar_hizlari):
        durum_kodu = None
        
        if hiz > ust_esik:
            durum_kodu = "ANOMALI_YUKSEK"
            sapma_yuzdesi = ((hiz - ortalama_hiz) / ortalama_hiz) * 100
            
            neden = []
            if i > 0 and ruzgar_hizlari[i-1] < ortalama_hiz:
                neden.append("Ani rüzgar artışı - Atmosferik değişim")
            
            if sicakliklar[i] < statistics.mean(sicakliklar) - 2:
                neden.append("Düşük sıcaklık korelasyonu")
            
            if hiz >= max_hiz * 0.9:
                neden.append("Dönem maksimum seviyesine yakın")
            
            if not neden:
                neden.append("Standart meteorolojik varyasyon")
            
            anomaliler.append({
                "zaman": zaman_damgalari[i],
                "hiz": hiz,
                "yon": ruzgar_yonleri[i],
                "durum_kodu": DURUM_KODLARI[durum_kodu]["kod"],
                "durum": durum_kodu,
                "sapma_yuzdesi": round(sapma_yuzdesi, 2),
                "ortalamadan_fark": round(hiz - ortalama_hiz, 2),
                "neden_analizi": neden
            })
        
        elif hiz < alt_esik and alt_esik > 0:
            durum_kodu = "ANOMALI_DUSUK"
            sapma_yuzdesi = ((ortalama_hiz - hiz) / ortalama_hiz) * 100
            
            neden = []
            if i > 0 and ruzgar_hizlari[i-1] > ortalama_hiz:
                neden.append("Ani sakinleşme")
            
            if sicakliklar[i] > statistics.mean(sicakliklar) + 2:
                neden.append("Yüksek sıcaklık korelasyonu")
            
            if not neden:
                neden.append("Rüzgar sakinliği")
            
            anomaliler.append({
                "zaman": zaman_damgalari[i],
                "hiz": hiz,
                "yon": ruzgar_yonleri[i],
                "durum_kodu": DURUM_KODLARI[durum_kodu]["kod"],
                "durum": durum_kodu,
                "sapma_yuzdesi": round(sapma_yuzdesi, 2),
                "ortalamadan_fark": round(ortalama_hiz - hiz, 2),
                "neden_analizi": neden
            })
    
    if verbose and console and anomaliler:
        anomali_table = Table(title="⚠️  Tespit Edilen Anomaliler", box=box.DOUBLE)
        anomali_table.add_column("Zaman", style="cyan")
        anomali_table.add_column("Hız", justify="right")
        anomali_table.add_column("Durum", style="bold")
        anomali_table.add_column("Sapma %", justify="right")
        
        for anomali in anomaliler[:10]:
            durum = anomali['durum']
            renk = DURUM_KODLARI[durum]['renk']
            anomali_table.add_row(
                anomali['zaman'],
                f"{anomali['hiz']} km/h",
                f"[{renk}]{durum}[/{renk}]",
                f"{anomali['sapma_yuzdesi']:.1f}%"
            )
        
        console.print(anomali_table)
    
    # === RÜZGAR HIZ TRENDLERİ ===
    hiz_artis_periyotlari = []
    hiz_azalis_periyotlari = []
    sabit_periyotlar = []
    
    i = 0
    while i < len(ruzgar_hizlari) - 1:
        baslangic = i
        trend = None
        trend_durum_kodu = None
        
        if ruzgar_hizlari[i+1] > ruzgar_hizlari[i] + 1:
            trend = "ARTIS"
            trend_durum_kodu = "TREND_ARTIS"
            while i < len(ruzgar_hizlari) - 1 and ruzgar_hizlari[i+1] >= ruzgar_hizlari[i]:
                i += 1
        elif ruzgar_hizlari[i+1] < ruzgar_hizlari[i] - 1:
            trend = "AZALIS"
            trend_durum_kodu = "TREND_AZALIS"
            while i < len(ruzgar_hizlari) - 1 and ruzgar_hizlari[i+1] <= ruzgar_hizlari[i]:
                i += 1
        else:
            trend = "SABIT"
            trend_durum_kodu = "TREND_SABIT"
            while i < len(ruzgar_hizlari) - 1 and abs(ruzgar_hizlari[i+1] - ruzgar_hizlari[i]) <= 1:
                i += 1
        
        bitis = i
        
        if bitis > baslangic:
            periyot = {
                "baslangic_saat": zaman_damgalari[baslangic],
                "bitis_saat": zaman_damgalari[bitis],
                "baslangic_hiz": ruzgar_hizlari[baslangic],
                "bitis_hiz": ruzgar_hizlari[bitis],
                "degisim": round(ruzgar_hizlari[bitis] - ruzgar_hizlari[baslangic], 2),
                "sure_saat": bitis - baslangic,
                "ortalama_hiz": round(statistics.mean(ruzgar_hizlari[baslangic:bitis+1]), 2),
                "durum_kodu": DURUM_KODLARI[trend_durum_kodu]["kod"],
                "durum": trend_durum_kodu
            }
            
            if trend == "ARTIS":
                hiz_artis_periyotlari.append(periyot)
            elif trend == "AZALIS":
                hiz_azalis_periyotlari.append(periyot)
            else:
                sabit_periyotlar.append(periyot)
        
        i += 1
    
    if verbose and console:
        trend_tree = Tree("📈 [bold]Trend Analizi[/bold]")
        
        artis_branch = trend_tree.add(f"[yellow]↗️  Artış Periyotları ({len(hiz_artis_periyotlari)})[/yellow]")
        for p in hiz_artis_periyotlari[:5]:
            artis_branch.add(f"{p['baslangic_saat']} → {p['bitis_saat']}: {p['baslangic_hiz']}→{p['bitis_hiz']} km/h")
        
        azalis_branch = trend_tree.add(f"[blue]↘️  Azalış Periyotları ({len(hiz_azalis_periyotlari)})[/blue]")
        for p in hiz_azalis_periyotlari[:5]:
            azalis_branch.add(f"{p['baslangic_saat']} → {p['bitis_saat']}: {p['baslangic_hiz']}→{p['bitis_hiz']} km/h")
        
        sabit_branch = trend_tree.add(f"[green]→ Sabit Periyotlar ({len(sabit_periyotlar)})[/green]")
        for p in sabit_periyotlar[:5]:
            sabit_branch.add(f"{p['baslangic_saat']} → {p['bitis_saat']}: ~{p['ortalama_hiz']} km/h")
        
        console.print(trend_tree)
    
    # === RÜZGAR YÖN ANALİZİ ===
    yon_frekans = {}
    for yon in ruzgar_yonleri:
        yon_frekans[yon] = yon_frekans.get(yon, 0) + 1
    
    hakim_yon = max(yon_frekans, key=yon_frekans.get)
    yon_dagilim = [
        {
            "yon": yon,
            "frekans": frekans,
            "yuzde": round((frekans / len(ruzgar_yonleri)) * 100, 2)
        }
        for yon, frekans in sorted(yon_frekans.items(), key=lambda x: x[1], reverse=True)
    ]
    
    if verbose and console:
        yon_table = Table(title="🧭 Rüzgar Yönü Dağılımı", box=box.SIMPLE)
        yon_table.add_column("Yön", style="cyan")
        yon_table.add_column("Frekans", justify="right")
        yon_table.add_column("Yüzde", justify="right", style="yellow")
        
        for yon_data in yon_dagilim:
            yon_table.add_row(
                yon_data['yon'],
                str(yon_data['frekans']),
                f"{yon_data['yuzde']:.1f}%"
            )
        
        console.print(yon_table)
    
    # === SAATLIK ANALİZ ===
    saat_analizi = []
    current_hour = None
    hour_speeds = []
    
    for entry in data:
        saat = entry['zaman']['saat']
        hiz = entry['ruzgar']['hiz']
        
        if current_hour is None:
            current_hour = saat
            hour_speeds = [hiz]
        elif saat == current_hour:
            hour_speeds.append(hiz)
        else:
            avg_hour_speed = statistics.mean(hour_speeds)
            
            if avg_hour_speed > ortalama_hiz + std_sapma:
                durum = "YUKSEK_RUZGAR"
            elif avg_hour_speed < ortalama_hiz - std_sapma:
                durum = "DUSUK_RUZGAR"
            else:
                durum = "NORMAL"
            
            saat_analizi.append({
                "saat": f"{current_hour:02d}:00",
                "ortalama_hiz": round(avg_hour_speed, 2),
                "durum": durum,
                "durum_kodu": DURUM_KODLARI[durum]["kod"],
                "veri_sayisi": len(hour_speeds)
            })
            
            current_hour = saat
            hour_speeds = [hiz]
    
    if hour_speeds:
        avg_hour_speed = statistics.mean(hour_speeds)
        
        if avg_hour_speed > ortalama_hiz + std_sapma:
            durum = "YUKSEK_RUZGAR"
        elif avg_hour_speed < ortalama_hiz - std_sapma:
            durum = "DUSUK_RUZGAR"
        else:
            durum = "NORMAL"
        
        saat_analizi.append({
            "saat": f"{current_hour:02d}:00",
            "ortalama_hiz": round(avg_hour_speed, 2),
            "durum": durum,
            "durum_kodu": DURUM_KODLARI[durum]["kod"],
            "veri_sayisi": len(hour_speeds)
        })
    
    if verbose and console:
        saat_table = Table(title="⏰ Saatlik Durum", box=box.HORIZONTALS)
        saat_table.add_column("Saat", style="cyan")
        saat_table.add_column("Ort. Hız", justify="right")
        saat_table.add_column("Durum", style="bold")
        
        for saat_data in saat_analizi:
            durum = saat_data['durum']
            renk = DURUM_KODLARI[durum]['renk']
            saat_table.add_row(
                saat_data['saat'],
                f"{saat_data['ortalama_hiz']} km/h",
                f"[{renk}]{durum}[/{renk}]"
            )
        
        console.print(saat_table)
    
    if verbose and console:
        console.print(Panel.fit(
            f"[bold green]✓ Analiz tamamlandı![/bold green]\n"
            f"[dim]Genel Durum: {genel_durum} (Kod: {DURUM_KODLARI[genel_durum]['kod']})[/dim]",
            border_style="green"
        ))
    
    # === SON RAPOR ===
    rapor = {
        "rapor_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "durum": "BAŞARILI",
        "genel_durum": {
            "durum": genel_durum,
            "durum_kodu": DURUM_KODLARI[genel_durum]["kod"],
            "aciklama": DURUM_KODLARI[genel_durum]["aciklama"]
        },
        "analiz_kapsami": {
            "toplam_veri_noktasi": len(data),
            "baslangic_zamani": zaman_damgalari[0] if zaman_damgalari else "Bilinmiyor",
            "bitis_zamani": zaman_damgalari[-1] if zaman_damgalari else "Bilinmiyor"
        },
        "istatistiksel_ozet": {
            "ortalama_ruzgar_hizi_kmh": round(ortalama_hiz, 2),
            "medyan_ruzgar_hizi_kmh": round(medyan_hiz, 2),
            "minimum_ruzgar_hizi_kmh": min_hiz,
            "maksimum_ruzgar_hizi_kmh": max_hiz,
            "standart_sapma": round(std_sapma, 2),
            "volatilite_orani_yuzde": round(volatilite_orani, 2),
            "ust_anomali_esigi_kmh": round(ust_esik, 2),
            "alt_anomali_esigi_kmh": round(alt_esik, 2)
        },
        "yon_analizi": {
            "hakim_ruzgar_yonu": hakim_yon,
            "yon_dagilimi": yon_dagilim
        },
        "anomali_raporu": {
            "toplam_anomali_sayisi": len(anomaliler),
            "anomali_orani_yuzde": round((len(anomaliler) / len(data)) * 100, 2),
            "tespit_edilen_anomaliler": anomaliler
        },
        "trend_analizi": {
            "artis_periyotlari": hiz_artis_periyotlari,
            "azalis_periyotlari": hiz_azalis_periyotlari,
            "sabit_periyotlar": sabit_periyotlar
        },
        "saatlik_analiz": saat_analizi,
        "durum_kodlari_referans": DURUM_KODLARI
    }
    
    # === OUTPUT FORMAT İŞLEME ===
    if output_format:
        output_format = output_format.upper()
        
        if output_format == "HTML":
            html_content = _generate_html_report(rapor, anomaliler, saat_analizi, yon_dagilim)
            rapor["content"] = html_content
            
        elif output_format == "TXT":
            txt_content = _generate_txt_report(rapor, anomaliler, saat_analizi, yon_dagilim)
            rapor["content"] = txt_content
    
    # === SVG KAYDETME ===
    if save_svg and console and RICH_AVAILABLE:
        try:
            console.save_svg(save_svg, title="Rüzgar Analiz Raporu")
            rapor["svg_dosya_yolu"] = save_svg
        except Exception as e:
            rapor["svg_hata"] = f"SVG kaydedilemedi: {str(e)}"
    
    return rapor

def _generate_html_report(rapor, anomaliler, saat_analizi, yon_dagilim):
    """HTML formatında rapor oluşturur"""
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rüzgar Analiz Raporu</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .back-link {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            color: white;
            padding: 12px 20px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            border: 1px solid rgba(255, 255, 255, 0.3);
            transition: all 0.3s ease;
            z-index: 1000;
        }}
        .back-link:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateX(-5px);
        }}
        .container {{
            max-width: 1200px;
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
            margin-bottom: 30px;
            font-size: 1.1em;
        }}
        h2 {{
            color: #2c3e50;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .stat-boxes {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 30px 0;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease;
        }}
        .stat-box:hover {{
            transform: translateY(-5px);
        }}
        .stat-box .label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }}
        .stat-box .value {{
            font-size: 1.8em;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
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
        tbody tr {{
            transition: all 0.3s ease;
        }}
        tbody tr:hover {{
            background: #f8f9fa;
            transform: scale(1.01);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}
        tbody tr:last-child td {{
            border-bottom: none;
        }}
        .anomali-yuksek {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .anomali-dusuk {{
            color: #3498db;
            font-weight: bold;
        }}
        .normal {{
            color: #27ae60;
            font-weight: bold;
        }}
        .yuksek-ruzgar {{
            color: #e67e22;
            font-weight: bold;
        }}
        .dusuk-ruzgar {{
            color: #16a085;
            font-weight: bold;
        }}
        @media (max-width: 768px) {{
            .container {{
                padding: 20px;
                margin-top: 60px;
            }}
            h1 {{
                font-size: 1.8em;
            }}
            .stat-boxes {{
                grid-template-columns: 1fr;
            }}
            th, td {{
                padding: 10px;
                font-size: 0.9em;
            }}
        }}
    </style>
</head>
<body>
    <a href="saatlik.html" class="back-link">← Geri</a>
    
    <div class="container">
        <h1>🌪️ RÜZGAR ANALİZ RAPORU</h1>
        <p class="subtitle">Detaylı Meteorolojik Analiz • {rapor['rapor_zamani']}</p>
        
        <h2>📊 İstatistiksel Özet</h2>
        <div class="stat-boxes">
            <div class="stat-box">
                <div class="label">Ortalama Hız</div>
                <div class="value">{rapor['istatistiksel_ozet']['ortalama_ruzgar_hizi_kmh']} km/h</div>
            </div>
            <div class="stat-box">
                <div class="label">Maksimum Hız</div>
                <div class="value">{rapor['istatistiksel_ozet']['maksimum_ruzgar_hizi_kmh']} km/h</div>
            </div>
            <div class="stat-box">
                <div class="label">Minimum Hız</div>
                <div class="value">{rapor['istatistiksel_ozet']['minimum_ruzgar_hizi_kmh']} km/h</div>
            </div>
            <div class="stat-box">
                <div class="label">Volatilite</div>
                <div class="value">{rapor['istatistiksel_ozet']['volatilite_orani_yuzde']}%</div>
            </div>
        </div>
        
        <h2>⚠️ Anomaliler (Toplam: {len(anomaliler)})</h2>
        <table>
            <thead>
                <tr>
                    <th>⏰ Zaman</th>
                    <th>💨 Hız</th>
                    <th>🧭 Yön</th>
                    <th>📊 Durum</th>
                    <th style="text-align:center;">📈 Sapma %</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for anomali in anomaliler[:15]:
        durum_class = "anomali-yuksek" if "YUKSEK" in anomali['durum'] else "anomali-dusuk"
        html += f"""
                <tr>
                    <td>{anomali['zaman']}</td>
                    <td>{anomali['hiz']} km/h</td>
                    <td>{anomali['yon']}</td>
                    <td class="{durum_class}">{anomali['durum']}</td>
                    <td style="text-align:center;">{anomali['sapma_yuzdesi']}%</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
        
        <h2>⏰ Saatlik Analiz</h2>
        <table>
            <thead>
                <tr>
                    <th>🕐 Saat</th>
                    <th style="text-align:center;">💨 Ortalama Hız</th>
                    <th style="text-align:center;">📊 Durum</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for saat in saat_analizi:
        durum_class = "normal"
        if saat['durum'] == "YUKSEK_RUZGAR":
            durum_class = "yuksek-ruzgar"
        elif saat['durum'] == "DUSUK_RUZGAR":
            durum_class = "dusuk-ruzgar"
            
        html += f"""
                <tr>
                    <td>{saat['saat']}</td>
                    <td style='text-align:center;'>{saat['ortalama_hiz']} km/h</td>
                    <td style='text-align:center;' class="{durum_class}">{saat['durum']}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
        
        <h2>🧭 Rüzgar Yönü Dağılımı</h2>
        <table>
            <thead>
                <tr>
                    <th>🧭 Yön</th>
                    <th style="text-align:center;">📊 Frekans</th>
                    <th style="text-align:center;">📈 Yüzde</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for yon in yon_dagilim:
        html += f"""
                <tr>
                    <td>{yon['yon']}</td>
                    <td style='text-align:center;'>{yon['frekans']}</td>
                    <td style='text-align:center;'>{yon['yuzde']}%</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
    """
    
    return html

def _generate_txt_report(rapor, anomaliler, saat_analizi, yon_dagilim):
    """TXT formatında kullanışlı rapor oluşturur"""
    txt = f"""
================================================================================
                        RÜZGAR ANALİZ RAPORU
================================================================================
Rapor Zamanı: {rapor['rapor_zamani']}
Genel Durum: {rapor['genel_durum']['durum']} (Kod: {rapor['genel_durum']['durum_kodu']})

--------------------------------------------------------------------------------
İSTATİSTİKSEL ÖZET
--------------------------------------------------------------------------------
Ortalama Rüzgar Hızı    : {rapor['istatistiksel_ozet']['ortalama_ruzgar_hizi_kmh']} km/h
Medyan Hız              : {rapor['istatistiksel_ozet']['medyan_ruzgar_hizi_kmh']} km/h
Minimum Hız             : {rapor['istatistiksel_ozet']['minimum_ruzgar_hizi_kmh']} km/h
Maksimum Hız            : {rapor['istatistiksel_ozet']['maksimum_ruzgar_hizi_kmh']} km/h
Standart Sapma          : {rapor['istatistiksel_ozet']['standart_sapma']}
Volatilite Oranı        : {rapor['istatistiksel_ozet']['volatilite_orani_yuzde']}%

--------------------------------------------------------------------------------
ANOMALİLER (Toplam: {len(anomaliler)})
--------------------------------------------------------------------------------
"""
    
    for i, anomali in enumerate(anomaliler[:10], 1):
        txt += f"""
{i}. {anomali['zaman']}
   Hız: {anomali['hiz']} km/h | Yön: {anomali['yon']} | Durum: {anomali['durum']}
   Sapma: {anomali['sapma_yuzdesi']}% | Fark: {anomali['ortalamadan_fark']} km/h
   Neden: {', '.join(anomali['neden_analizi'])}
"""
    
    txt += """
--------------------------------------------------------------------------------
SAATLİK ANALİZ
--------------------------------------------------------------------------------
"""
    
    for saat in saat_analizi:
        txt += f"{saat['saat']}: {saat['ortalama_hiz']} km/h [{saat['durum']}]\n"
    
    txt += f"""
--------------------------------------------------------------------------------
RÜZGAR YÖNÜ DAĞILIMI
--------------------------------------------------------------------------------
Hakim Yön: {rapor['yon_analizi']['hakim_ruzgar_yonu']}

"""
    
    for yon in yon_dagilim:
        txt += f"{yon['yon']:>10s}: {yon['frekans']:>3d} kez ({yon['yuzde']:>5.1f}%)\n"
    
    txt += "\n" + "="*80 + "\n"
    
    return txt

# === KULLANIM ÖRNEĞİ ===
if __name__ == "__main__":
    # getData fonksiyonunun tanımlı olduğunu varsayıyoruz
    # test_url = "https://havadurumu15gunluk.xyz/saat-saat-havadurumu/0/293/bursa-hava-durumu-saatlik.html"
    # data = getData(test_url, verbose=True)
    
    # Test için örnek veri
    data = [
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "10:00", "saat": 10, "dakika": 0}, "durum": "Sağanak yağışlı", "sicaklik": 6, "hissedilen": 4, "ruzgar": {"yon": "GGD", "hiz": 11}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "11:00", "saat": 11, "dakika": 0}, "durum": "Sağanak yağışlı", "sicaklik": 7, "hissedilen": 5, "ruzgar": {"yon": "GGD", "hiz": 11}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "12:00", "saat": 12, "dakika": 0}, "durum": "Çok Bulutlu", "sicaklik": 8, "hissedilen": 6, "ruzgar": {"yon": "GGD", "hiz": 11}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "13:00", "saat": 13, "dakika": 0}, "durum": "Parçalı Bulutlu", "sicaklik": 9, "hissedilen": 7, "ruzgar": {"yon": "GD", "hiz": 13}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "14:00", "saat": 14, "dakika": 0}, "durum": "Parçalı Bulutlu", "sicaklik": 10, "hissedilen": 8, "ruzgar": {"yon": "GD", "hiz": 15}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "15:00", "saat": 15, "dakika": 0}, "durum": "Az Bulutlu", "sicaklik": 9, "hissedilen": 7, "ruzgar": {"yon": "GD", "hiz": 22}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "16:00", "saat": 16, "dakika": 0}, "durum": "Çok Bulutlu", "sicaklik": 8, "hissedilen": 5, "ruzgar": {"yon": "GGD", "hiz": 18}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "17:00", "saat": 17, "dakika": 0}, "durum": "Çok Bulutlu", "sicaklik": 7, "hissedilen": 4, "ruzgar": {"yon": "GGD", "hiz": 14}},
        {"tarih": "3 Ocak Cumartesi", "zaman": {"tam": "18:00", "saat": 18, "dakika": 0}, "durum": "Çok Bulutlu", "sicaklik": 6, "hissedilen": 3, "ruzgar": {"yon": "G", "hiz": 12}},
    ]
    
    # Verbose modda çalıştır
    print("\n=== VERBOSE MODE ===\n")
    sonuc = windanalysis(data, verbose=True)
    
    print("\n=== JSON ÇIKTI ===\n")
    print(json.dumps(sonuc, indent=2, ensure_ascii=False))

    # 2. HTML içerikli rapor
    rapor = windanalysis(data, verbose=True, output_format="HTML")
    with open("rapor.html", "w", encoding="utf-8") as f:
        f.write(rapor["content"])

    # 3. TXT içerikli rapor
    rapor = windanalysis(data, verbose=True, output_format="TXT")
    print(rapor["content"])

    rapor = windanalysis(data, verbose=True, save_svg="analiz_raporu.svg")
    print(f"SVG kaydedildi: {rapor['svg_dosya_yolu']}")

















from typing import Dict, Any
from datetime import datetime

def ruzgaranaliz_reply(windanaliz_data: Dict[str, Any], type: str = "Normal") -> str:
    """
    Rüzgar analiz verisini kullanıcı dostu metne dönüştürür.
    
    Args:
        windanaliz_data: windanalysis() fonksiyonundan dönen veri
        type: "HTML", "Normal", "TXT"
    
    Returns:
        Formatlanmış metin
    """
    
    if windanaliz_data.get("durum") != "BAŞARILI":
        return "Rüzgar verisi alınamadı."
    
    # Veri çıkarma
    genel = windanaliz_data['genel_durum']
    stats = windanaliz_data['istatistiksel_ozet']
    anomaliler = windanaliz_data['anomali_raporu']['tespit_edilen_anomaliler']
    trendler = windanaliz_data['trend_analizi']
    saatlik = windanaliz_data['saatlik_analiz']
    yon = windanaliz_data['yon_analizi']
    
    # Tarih belirleme
    tarih_str = windanaliz_data['analiz_kapsami']['baslangic_zamani']
    bugun = datetime.now().date()
    
    try:
        analiz_tarih = datetime.strptime(tarih_str.split()[0], "%d").date().replace(
            year=bugun.year, month=bugun.month
        )
        if analiz_tarih == bugun:
            tarih_label = "Bugün"
        elif (analiz_tarih - bugun).days == 1:
            tarih_label = "Yarın"
        elif (analiz_tarih - bugun).days == 2:
            tarih_label = "2 Gün Sonra"
        elif (analiz_tarih - bugun).days <= 7:
            tarih_label = f"{(analiz_tarih - bugun).days} Gün Sonra"
        else:
            tarih_label = "İleri Tarih"
    except:
        tarih_label = "Bugün"
    
    # Genel durum değerlendirmesi
    durum_kodu = genel['durum_kodu']
    ortalama = stats['ortalama_ruzgar_hizi_kmh']
    max_hiz = stats['maksimum_ruzgar_hizi_kmh']
    min_hiz = stats['minimum_ruzgar_hizi_kmh']
    hakim_yon = yon['hakim_ruzgar_yonu']
    
    # Şiddetli rüzgar saatleri
    siddetli_saatler = [s for s in saatlik if s['durum'] in ['YUKSEK_RUZGAR', 'ANOMALI_YUKSEK']]
    
    # Yüksek anomali saatleri
    yuksek_anomaliler = [a for a in anomaliler if a['durum'] == 'ANOMALI_YUKSEK']
    
    # Artış periyotları
    artis_periyotlari = trendler['artis_periyotlari']
    onemli_artislar = [a for a in artis_periyotlari if a['degisim'] >= 5]
    
    # === TİP: TXT ===
    if type == "TXT":
        txt = f"Tarih: {tarih_label}\n"
        txt += f"Ortalama Rüzgar: {ortalama:.0f} km/s\n"
        txt += f"Rüzgar Aralığı: {min_hiz}-{max_hiz} km/s\n"
        txt += f"Hakim Yön: {hakim_yon}\n"
        
        if siddetli_saatler:
            saat_liste = ", ".join([s['saat'] for s in siddetli_saatler])
            max_siddet = max([s['ortalama_hiz'] for s in siddetli_saatler])
            txt += f"Şiddetli Rüzgar Saatleri: {saat_liste} ({max_siddet:.0f} km/s'ye kadar)\n"
        else:
            txt += "Şiddetli Rüzgar: Yok\n"
        
        if yuksek_anomaliler:
            txt += f"Dikkat: {len(yuksek_anomaliler)} adet ani rüzgar artışı bekleniyor\n"
        
        if durum_kodu >= 3:
            txt += "⚠️ Dikkatli olun: Rüzgar koşulları istikrarsız\n"
        
        return txt
    
    # === TİP: HTML ===
    elif type == "HTML":
        html = f"<div class='ruzgar-analiz'>\n"
        html += f"<h3>🌪️ Rüzgar Durumu - {tarih_label}</h3>\n"
        
        # Genel durum
        if durum_kodu <= 1:
            renk = "#4CAF50"
            durum_text = "Sakin"
        elif durum_kodu == 2:
            renk = "#FF9800"
            durum_text = "Orta Şiddetli"
        else:
            renk = "#F44336"
            durum_text = "Dikkat Gerekli"
        
        html += f"<p style='color: {renk}; font-weight: bold;'>Genel Durum: {durum_text}</p>\n"
        
        # İstatistikler
        html += "<div class='stats'>\n"
        html += f"<p><strong>Ortalama Hız:</strong> {ortalama:.0f} km/s</p>\n"
        html += f"<p><strong>Rüzgar Aralığı:</strong> {min_hiz}-{max_hiz} km/s</p>\n"
        html += f"<p><strong>Hakim Yön:</strong> {hakim_yon}</p>\n"
        html += "</div>\n"
        
        # Şiddetli saatler
        if siddetli_saatler:
            html += "<div class='uyari' style='background: #FFF3CD; padding: 10px; border-left: 4px solid #FF9800; margin: 10px 0;'>\n"
            html += "<h4>⚠️ Şiddetli Rüzgar Saatleri</h4>\n"
            html += "<ul>\n"
            for saat in siddetli_saatler:
                html += f"<li><strong>{saat['saat']}</strong> - {saat['ortalama_hiz']:.0f} km/s</li>\n"
            html += "</ul>\n"
            
            if yuksek_anomaliler:
                html += "<p><em>Bu saatlerde ani rüzgar artışları beklenebilir.</em></p>\n"
            
            html += "</div>\n"
        
        # Önemli artışlar
        if onemli_artislar:
            html += "<div class='trend' style='background: #E3F2FD; padding: 10px; border-left: 4px solid #2196F3; margin: 10px 0;'>\n"
            html += "<h4>📈 Rüzgar Artış Periyotları</h4>\n"
            html += "<ul>\n"
            for artis in onemli_artislar[:3]:
                html += f"<li>{artis['baslangic_saat']} - {artis['bitis_saat']}: "
                html += f"{artis['baslangic_hiz']} → {artis['bitis_hiz']} km/s (+{artis['degisim']:.0f} km/s)</li>\n"
            html += "</ul>\n"
            html += "</div>\n"
        
        # Yön değişimi
        if len(yon['yon_dagilimi']) > 2:
            html += "<div class='yon-info'>\n"
            html += f"<p><small>Rüzgar yönü değişken olacak. Hakim: {hakim_yon}</small></p>\n"
            html += "</div>\n"
        
        html += "</div>\n"
        return html
    
    # === TİP: Normal (Doğal Metin) ===
    else:
        # Sakin durum
        if durum_kodu <= 1 and max_hiz < 20:
            metin = f"{tarih_label} rüzgar oldukça sakin geçecek. "
            metin += f"Ortalama {ortalama:.0f} km/s civarında esecek rüzgar, "
            metin += f"{hakim_yon} yönünden gelecek. "
            
            if max_hiz < 15:
                metin += "Günün tamamı boyunca rüzgar hissi minimal seviyede olacak. "
            else:
                metin += f"En yüksek {max_hiz} km/s'ye ulaşacak ama bu bile rahatsız edici olmayacak. "
            
            return metin
        
        # Orta şiddetli
        elif durum_kodu == 2 or (20 <= max_hiz < 30):
            metin = f"{tarih_label} rüzgar orta şiddette esecek. "
            metin += f"Genel olarak {ortalama:.0f} km/s civarında seyreden rüzgar, "
            metin += f"{hakim_yon} yönünden geliyor olacak. "
            
            if siddetli_saatler:
                saat_baslangic = siddetli_saatler[0]['saat']
                saat_bitis = siddetli_saatler[-1]['saat']
                max_siddet = max([s['ortalama_hiz'] for s in siddetli_saatler])
                
                metin += f"Özellikle {saat_baslangic} - {saat_bitis} saatleri arasında "
                metin += f"{max_siddet:.0f} km/s'ye kadar çıkacak. "
            
            if onemli_artislar:
                en_buyuk_artis = max(onemli_artislar, key=lambda x: x['degisim'])
                metin += f"{en_buyuk_artis['baslangic_saat']} civarında ani bir artış yaşanacak, "
                metin += f"bu {hakim_yon} yönünden gelen hava kütlesinin etkisi. "
            
            metin += "Hafif etkili olabilir, dışarıda dikkatli olun."
            
            return metin
        
        # Şiddetli/İstikrarsız
        else:
            metin = f"{tarih_label} için rüzgar koşulları dikkat gerektiriyor. "
            metin += f"Rüzgar {min_hiz}-{max_hiz} km/s aralığında değişken olacak. "
            
            if yuksek_anomaliler:
                metin += f"Gün boyunca {len(yuksek_anomaliler)} farklı noktada ani rüzgar artışları bekleniyor. "
            
            if siddetli_saatler:
                saat_liste = ", ".join([s['saat'] for s in siddetli_saatler[:3]])
                max_siddet = max([s['ortalama_hiz'] for s in siddetli_saatler])
                
                metin += f"En şiddetli periyot {saat_liste} saatleri arasında, "
                metin += f"rüzgar {max_siddet:.0f} km/s'ye kadar çıkacak. "
            
            # Neden analizi
            if yuksek_anomaliler and yuksek_anomaliler[0].get('neden_analizi'):
                ilk_neden = yuksek_anomaliler[0]['neden_analizi'][0]
                if "atmosferik" in ilk_neden.lower() or "basınç" in ilk_neden.lower():
                    metin += "Bu artışın sebebi atmosferik basınç değişimi. "
                elif "cephe" in ilk_neden.lower():
                    metin += "Muhtemelen bir hava cephesi etkili olacak. "
            
            metin += f"Rüzgar ağırlıklı olarak {hakim_yon} yönünden esecek. "
            
            # Volatilite uyarısı
            if stats['volatilite_orani_yuzde'] > 30:
                metin += "Rüzgar hızı oldukça değişken olacak, ani değişikliklere karşı hazırlıklı olun. "
            
            metin += "Dışarıda vakit geçirecekseniz dikkatli olmanızı öneririm."
            
            return metin


# === TEST ===
if __name__ == "__main__":
    # Örnek windanaliz_data
    data = {
        "durum": "BAŞARILI",
        "genel_durum": {
            "durum": "YUKSEK_RUZGAR",
            "durum_kodu": 2,
            "aciklama": "Ortalamanın üstünde rüzgar"
        },
        "analiz_kapsami": {
            "baslangic_zamani": "10:00",
            "bitis_zamani": "18:00"
        },
        "istatistiksel_ozet": {
            "ortalama_ruzgar_hizi_kmh": 14.5,
            "minimum_ruzgar_hizi_kmh": 11,
            "maksimum_ruzgar_hizi_kmh": 22,
            "volatilite_orani_yuzde": 25.3
        },
        "yon_analizi": {
            "hakim_ruzgar_yonu": "GGD",
            "yon_dagilimi": [
                {"yon": "GGD", "frekans": 5, "yuzde": 55.6},
                {"yon": "GD", "frekans": 3, "yuzde": 33.3},
                {"yon": "G", "frekans": 1, "yuzde": 11.1}
            ]
        },
        "anomali_raporu": {
            "tespit_edilen_anomaliler": [
                {
                    "zaman": "15:00",
                    "hiz": 22,
                    "yon": "GD",
                    "durum": "ANOMALI_YUKSEK",
                    "neden_analizi": ["Ani rüzgar artışı - Atmosferik değişim"]
                }
            ]
        },
        "trend_analizi": {
            "artis_periyotlari": [
                {
                    "baslangic_saat": "13:00",
                    "bitis_saat": "15:00",
                    "baslangic_hiz": 13,
                    "bitis_hiz": 22,
                    "degisim": 9
                }
            ]
        },
        "saatlik_analiz": [
            {"saat": "10:00", "ortalama_hiz": 11, "durum": "NORMAL"},
            {"saat": "15:00", "ortalama_hiz": 22, "durum": "YUKSEK_RUZGAR"},
            {"saat": "16:00", "ortalama_hiz": 18, "durum": "YUKSEK_RUZGAR"}
        ]
    }
    
    print("=== NORMAL ===")
    print(ruzgaranaliz_reply(data, type="Normal"))
    
    print("\n=== TXT ===")
    print(ruzgaranaliz_reply(data, type="TXT"))
    
    print("\n=== HTML ===")
    print(ruzgaranaliz_reply(data, type="HTML"))
