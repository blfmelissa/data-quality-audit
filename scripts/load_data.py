import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'games_db')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def load_bronze_data():
    engine = create_engine(CONNECTION_STRING)

    df = pd.read_excel('data/Bronze/games_brut.xlsx')
    print(f"Lignes: {len(df)}, Colonnes: {len(df.columns)}")

    column_mapping = {
        'AppID': 'app_id',
        'Name': 'name',
        'Release date': 'release_date',
        'Estimated owners': 'estimated_owners',
        'Peak CCU': 'peak_ccu',
        'Required age': 'required_age',
        'Price': 'price',
        'Discount': 'discount',
        'DLC count': 'dlc_count',
        'About the game': 'about_the_game',
        'Supported languages': 'supported_languages',
        'Full audio languages': 'full_audio_languages',
        'Reviews': 'reviews',
        'Header image': 'header_image',
        'Website': 'website',
        'Support url': 'support_url',
        'Support email': 'support_email',
        'Windows': 'windows',
        'Mac': 'mac',
        'Linux': 'linux',
        'Metacritic score': 'metacritic_score',
        'Metacritic url': 'metacritic_url',
        'User score': 'user_score',
        'Positive': 'positive',
        'Negative': 'negative',
        'Score rank': 'score_rank',
        'Achievements': 'achievements',
        'Recommendations': 'recommendations',
        'Notes': 'notes',
        'Average playtime forever': 'average_playtime_forever',
        'Average playtime two weeks': 'average_playtime_two_weeks',
        'Median playtime forever': 'median_playtime_forever',
        'Median playtime two weeks': 'median_playtime_two_weeks',
        'Developers': 'developers',
        'Publishers': 'publishers',
        'Categories': 'categories',
        'Genres': 'genres',
        'Tags': 'tags',
        'Screenshots': 'screenshots',
        'Movies': 'movies'
    }

    df = df.rename(columns=column_mapping)

    df.to_sql('games_brut', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
    print(f"OK: {len(df)} lignes insérées dans games_brut")

if __name__ == '__main__':
    load_bronze_data()
