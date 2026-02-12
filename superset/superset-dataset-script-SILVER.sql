-- REQUÊTES SQL POUR SUPERSET - COUCHE clean

-- Dataset 1 : DQ_METRICS_TOTAL 

SELECT 
    -- 1. COMPLÉTUDE GLOBALE (Moyenne du taux de remplissage des 37 colonnes restantes)
    (
        (COUNT("app_id") + COUNT("name") + COUNT("release_date") + COUNT("estimated_owners") + 
         COUNT("peak_ccu") + COUNT("required_age") + COUNT("price") + COUNT("discount") + 
         COUNT("dlc_count") + COUNT("about_the_game") + COUNT("supported_languages") + 
         COUNT("full_audio_languages") + COUNT("reviews") + COUNT("header_image") + 
         COUNT("website") + COUNT("support_url") + COUNT("support_email") + COUNT("windows") + 
         COUNT("mac") + COUNT("linux") + COUNT("metacritic_score") + 
         COUNT("user_score") + COUNT("positive") + COUNT("negative") + 
         COUNT("achievements") + COUNT("recommendations") + COUNT("notes") + 
         COUNT("average_playtime_forever") + COUNT("average_playtime_two_weeks") + 
         COUNT("median_playtime_forever") + COUNT("median_playtime_two_weeks") + 
         COUNT("developers") + COUNT("publishers") + COUNT("categories") + COUNT("genres") + 
         COUNT("tags") + COUNT("screenshots"))::FLOAT 
        / (37 * COUNT(*)) * 100
    ) as score_completude,

    -- 2. UNICITÉ GLOBALE (Sur l'entité "Jeu", donc le Nom, par rapport au total)
    (COUNT(DISTINCT "name")::FLOAT / COUNT(*)::FLOAT) * 100 as score_unicite,

    -- 3. EXACTITUDE (Basé sur les formats emails invalides sur l'ensemble des lignes)
    100 - (
        COUNT(*) FILTER (WHERE "support_email" IS NOT NULL AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')::FLOAT 
        / NULLIF(COUNT("support_email"), 0) * 100
    ) as score_exactitude,

    -- 4. VALIDITÉ GLOBALE (Check basique : aucun prix ni temps de jeu ne doit être négatif)
    100 - (
        COUNT(*) FILTER (WHERE "price" < 0 OR "average_playtime_forever" < 0)::FLOAT
        / COUNT(*)::FLOAT * 100
    ) as score_validite,
    
    -- 5. COHÉRENCE (Règle F2P vs Prix sur toute la base)
    100 - (
        COUNT(*) FILTER (WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0)::FLOAT 
        / COUNT(*)::FLOAT * 100
    ) as score_coherence,

    -- 6. ACTUALITÉ
    100 as score_actualite

FROM games_clean;


-- Dataset 2 : DQ_TRENDS_HISTORY 

SELECT 
    DATE_TRUNC('year', release_date) as annee_sortie,
    COUNT(*) as volume_jeux,

    -- 1. COMPLÉTUDE (Calculée sur 37 colonnes)
    (
        (COUNT("app_id") + COUNT("name") + COUNT("release_date") + COUNT("estimated_owners") + 
         COUNT("peak_ccu") + COUNT("required_age") + COUNT("price") + COUNT("discount") + 
         COUNT("dlc_count") + COUNT("about_the_game") + COUNT("supported_languages") + 
         COUNT("full_audio_languages") + COUNT("reviews") + COUNT("header_image") + 
         COUNT("website") + COUNT("support_url") + COUNT("support_email") + COUNT("windows") + 
         COUNT("mac") + COUNT("linux") + COUNT("metacritic_score") + 
         COUNT("user_score") + COUNT("positive") + COUNT("negative") + 
         COUNT("achievements") + COUNT("recommendations") + COUNT("notes") + 
         COUNT("average_playtime_forever") + COUNT("average_playtime_two_weeks") + 
         COUNT("median_playtime_forever") + COUNT("median_playtime_two_weeks") + 
         COUNT("developers") + COUNT("publishers") + COUNT("categories") + COUNT("genres") + 
         COUNT("tags") + COUNT("screenshots"))::FLOAT 
        / (37 * NULLIF(COUNT(*), 0)) * 100
    ) as score_completude,

    -- 2. UNICITÉ (Unicité des noms au sein de l'année)
    (COUNT(DISTINCT "name")::FLOAT / NULLIF(COUNT(*), 0)::FLOAT) * 100 as score_unicite,

    -- 3. EXACTITUDE (Focus Email, identique au global)
    COALESCE(
        100 - (
            COUNT(*) FILTER (WHERE "support_email" IS NOT NULL AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')::FLOAT 
            / NULLIF(COUNT("support_email"), 0) * 100
        ), 100
    ) as score_exactitude,

    -- 4. VALIDITÉ (Prix ou Playtime négatifs)
    100 - (
        COUNT(*) FILTER (WHERE "price" < 0 OR "average_playtime_forever" < 0)::FLOAT
        / NULLIF(COUNT(*), 0)::FLOAT * 100
    ) as score_validite,

    -- 5. COHÉRENCE (F2P vs Prix)
    100 - (
        COUNT(*) FILTER (WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0)::FLOAT 
        / NULLIF(COUNT(*), 0)::FLOAT * 100
    ) as score_coherence,

    -- 6. ACTUALITÉ (Fixe à 100 comme dans ton global)
    100 as score_actualite,

    -- Métriques contextuelles pour tes graphiques (Boxplot/Heatmap)
    AVG("price") as prix_moyen,
    MAX("price") as prix_max

FROM games_clean
WHERE release_date IS NOT NULL 
  AND release_date BETWEEN '2000-01-01' AND '2026-01-01'
GROUP BY 1
ORDER BY 1;


-- Dataset 3 : DQ_ERROR_LIST 

-- Liste des jeux avec incohérence "Free to Play" mais payant
SELECT 
    app_id, 
    name, 
    'Cohérence' as pilier,
    'F2P avec Prix' as type_erreur, 
    CONCAT('Prix: ', price, '$ alors que le tag est Free to Play') as details,
    release_date
FROM games_clean 
WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0

UNION ALL

-- Liste des jeux avec Emails invalides (Exactitude)
SELECT 
    app_id, 
    name, 
    'Exactitude' as pilier,
    'Email Invalide' as type_erreur, 
    CONCAT('Email: ', support_email) as details,
    release_date
FROM games_clean 
WHERE "support_email" IS NOT NULL 
  AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

UNION ALL

-- Liste des jeux avec des Prix aberrants (Validité)
SELECT 
    app_id, 
    name, 
    'Validité' as pilier,
    'Prix Aberrant Non Flaggé' as type_erreur, 
    CONCAT('Prix: ', price, '$ (> 200$) mais price_outlier = FALSE') as details,
    release_date
FROM games_clean 
WHERE "price" > 200
AND (price_outlier = FALSE OR price_outlier IS NULL)

UNION ALL

-- Liste des jeux avec colonnes critiques manquantes (Complétude)
SELECT 
    app_id, 
    name, 
    'Complétude' as pilier,
    'Manque Info Critique' as type_erreur,
    'Tags manquants' as details,
    release_date
FROM games_clean
WHERE "tags" IS NULL;


-- Dataset 4 : DQ_SANKEY_FLOW 

-- Création des liens Source -> Target pour le Sankey
-- Etape 1 : Total vers Validité Structurelle (Exclusion des ID nuls ou doublons noms)
SELECT 
    'Total Dataset' as source, 
    'Validité Structurelle (Noms Uniques)' as target, 
    COUNT(DISTINCT name) as value 
FROM games_clean

UNION ALL

-- Etape 2 : Validité Structurelle vers Validité Métier (Exclusion des erreurs F2P)
SELECT 
    'Validité Structurelle (Noms Uniques)' as source, 
    'Cohérence Métier (Prix F2P OK)' as target, 
    COUNT(*) as value
FROM games_clean 
WHERE ("tags" NOT ILIKE '%Free to Play%' OR "price" = 0)

UNION ALL

-- Etape 3 : Cohérence vers Exactitude (Exclusion des mauvais emails)
SELECT 
    'Cohérence Métier (Prix F2P OK)' as source, 
    'Exactitude (Emails Valides)' as target, 
    COUNT(*) as value
FROM games_clean 
WHERE ("tags" NOT ILIKE '%Free to Play%' OR "price" = 0)
  AND ("support_email" IS NULL OR "support_email" ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

UNION ALL

-- Etape 4 : Le Reste (Les erreurs) pour équilibrer le graph
SELECT 'Total Dataset', 'Doublons/Erreurs ID', (COUNT(*) - COUNT(DISTINCT name)) FROM games_clean
UNION ALL
SELECT 'Validité Structurelle (Noms Uniques)', 'Erreurs Cohérence (F2P Payant)', COUNT(*) FROM games_clean WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0;


-- Dataset 5 : DQ_ZOOM_COMPLETENESS 

-- % de valeurs vides par colonne (pour audit de qualité des données)

-- ATTENTION : Ces 3 colonnes ont été supprimées dans games_clean, on ne les inclut plus :
-- - movies
-- - score_rank  
-- - metacritic_url

-- Scores / Reviews
SELECT 'metacritic_score' AS colonne, 100 - (COUNT(metacritic_score)::FLOAT / COUNT(*) * 100) AS pourcent_vide FROM games_clean
UNION ALL SELECT 'user_score', 100 - (COUNT(user_score)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Présence web / support
UNION ALL SELECT 'website', 100 - (COUNT(website)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'support_url', 100 - (COUNT(support_url)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'support_email', 100 - (COUNT(support_email)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Contenu éditorial
UNION ALL SELECT 'about_the_game', 100 - (COUNT(about_the_game)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'notes', 100 - (COUNT(notes)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'reviews', 100 - (COUNT(reviews)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Médias
UNION ALL SELECT 'header_image', 100 - (COUNT(header_image)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'screenshots', 100 - (COUNT(screenshots)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Classification / métadonnées
UNION ALL SELECT 'tags', 100 - (COUNT(tags)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'genres', 100 - (COUNT(genres)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'categories', 100 - (COUNT(categories)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Acteurs
UNION ALL SELECT 'developers', 100 - (COUNT(developers)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'publishers', 100 - (COUNT(publishers)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Langues
UNION ALL SELECT 'supported_languages', 100 - (COUNT(supported_languages)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'full_audio_languages', 100 - (COUNT(full_audio_languages)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Engagement / gameplay
UNION ALL SELECT 'achievements', 100 - (COUNT(achievements)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'recommendations', 100 - (COUNT(recommendations)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'average_playtime_forever', 100 - (COUNT(average_playtime_forever)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'average_playtime_two_weeks', 100 - (COUNT(average_playtime_two_weeks)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'median_playtime_forever', 100 - (COUNT(median_playtime_forever)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'median_playtime_two_weeks', 100 - (COUNT(median_playtime_two_weeks)::FLOAT / COUNT(*) * 100) FROM games_clean

-- Business
UNION ALL SELECT 'price', 100 - (COUNT(price)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'discount', 100 - (COUNT(discount)::FLOAT / COUNT(*) * 100) FROM games_clean
UNION ALL SELECT 'dlc_count', 100 - (COUNT(dlc_count)::FLOAT / COUNT(*) * 100) FROM games_clean

ORDER BY pourcent_vide DESC;


-- Dataset 6 : DQ_BOXPLOT 

SELECT 
    name,
    app_id, 
    price,
    CAST(EXTRACT(YEAR FROM release_date) AS INTEGER) AS annee_sortie
FROM games_clean
WHERE price >= 0
  AND release_date IS NOT NULL
  AND release_date BETWEEN DATE '2000-01-01' AND DATE '2026-01-01'
ORDER BY annee_sortie DESC;