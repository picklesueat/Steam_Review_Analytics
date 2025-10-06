# Models

* `bronze_trakt_comments.sql` – landing table with raw JSON and metadata columns (`resource_kind`, `page`, `payload_json`, etc.).
* `bronze_trakt_ratings_dist.sql` – landing table for aggregated rating distributions.
* `silver/stg_trakt__comment_event.sql` – typed staging model at the comment grain.
* `silver/stg_trakt__rating_dist.sql` – normalized rating distribution snapshots.
* `gold/fct_comment_daily.sql` – daily aggregated metrics powering breadth/intensity.
* `gold/mart_title_quadrants_daily.sql` – semantic metrics with quadrant classification.

Add `.sql` files for each model following the naming conventions above. Use YAML files to define tests and metrics.
