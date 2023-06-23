-- Table: concepts_with_counts  ----------------------------------------------------------------------------------------
DROP TABLE IF EXISTS {{schema}}concepts_with_counts;

CREATE TABLE IF NOT EXISTS {{schema}}concepts_with_counts AS (
    SELECT  concept_id,
            concept_name,
            domain_id,
            vocabulary_id,
            concept_class_id,
            standard_concept,
            concept_code,
            invalid_reason,
            COUNT(DISTINCT domain) AS domain_cnt,
            array_to_string(array_agg(domain), ',') AS domain,
            SUM(total_cnt) AS total_cnt,
            array_to_string(array_agg(distinct_person_cnt), ',') AS distinct_person_cnt
    FROM {{schema}}concepts_with_counts_ungrouped
    GROUP BY 1,2,3,4,5,6,7,8
    ORDER BY concept_id, domain );

CREATE INDEX cc_idx1 ON {{schema}}concepts_with_counts(concept_id);

-- this drop table is causing errors with the initialize script
-- @joeflack4: this table isn't needed after creating concepts_with_counts
-- DROP TABLE {{schema}}concepts_with_counts_ungrouped CASCADE;