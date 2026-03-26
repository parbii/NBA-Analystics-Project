from PIL import Image, ImageDraw
import pandas as pd

def create_elite_card(player, team, signal, pts):
    # 1. Vertical 9:16 Canvas
    img = Image.new('RGB', (1080, 1920), color=(5, 5, 15))
    draw = ImageDraw.Draw(img)
    
    # 2. Brand Colors
    neon_green = (57, 255, 20)
    neon_blue = (0, 255, 255)
    accent = neon_green if "HOT" in signal or "GREEN" in signal else neon_blue
    
    # 3. MIS Grid Design
    for i in range(0, 1080, 80):
        draw.line([(i, 0), (i, 1920)], fill=(20, 20, 45), width=2)
    for i in range(0, 1920, 80):
        draw.line([(0, i), (1080, i)], fill=(20, 20, 45), width=2)

    # 4. Content Layout
    draw.text((540, 200), "PARB'S PICKS", fill=(255, 255, 255), anchor="mm", font_size=130)
    draw.rectangle([300, 280, 780, 295], fill=accent)
    
    # Main Box
    draw.rectangle([100, 750, 980, 1400], fill=(15, 15, 35), outline=accent, width=10)
    draw.text((540, 950), player.upper(), fill=(255, 255, 255), anchor="mm", font_size=110)
    draw.text((540, 1100), f"TEAM: {team} | AVG: {pts} PPG", fill=(180, 180, 180), anchor="mm", font_size=60)
    
    # The Signal Badge
    draw.rectangle([200, 1550, 880, 1750], fill=accent)
    draw.text((540, 1650), signal, fill=(0, 0, 0), anchor="mm", font_size=90)
    
    img.save('parb_elite_pick.png')
    print("🔥 Elite Thumbnail Generated: parb_elite_pick.png")

# AUTO-RUN
try:
    df = pd.read_csv('parbs_picks_global_report.csv')
    top_play = df.iloc[0] # Get the #1 scorer for the thumbnail
    create_elite_card(top_play['PLAYER'], top_play['TEAM_ABBR'], top_play['SIGNAL'], top_play['PTS'])
except:
    create_elite_card("ANTHONY EDWARDS", "MIN", "🔥 GREEN LIGHT", "29.6")