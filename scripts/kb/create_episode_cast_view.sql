
DROP VIEW IF EXISTS episode_cast;

CREATE VIEW episode_cast AS
SELECT
    e.id AS episode_db_id,
    e.episode_id,
    e.absolute_number,
    e.season_number,
    e.episode_number,
    e.title_original,
    e.title_ru,

    c.id AS character_db_id,
    c.character_id,
    c.name_original AS character_name_original,
    c.name_ru AS character_name_ru,

    cem.role_type,
    cem.confidence,
    cem.evidence

FROM character_episode_mentions cem

JOIN episodes e
    ON e.id = cem.episode_id

JOIN characters c
    ON c.id = cem.character_id;

