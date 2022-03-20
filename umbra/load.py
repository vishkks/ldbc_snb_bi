import psycopg2
import sys
import os
import re
import time

if len(sys.argv) < 2:
    print("Umbra loader script")
    print("Usage: load.py <UMBRA_DATA_DIR> [--compressed]")
    exit(1)

data_dir = sys.argv[1]
local = len(sys.argv) == 3 and sys.argv[2] == "--local"

pg_con = psycopg2.connect(host="localhost", user="postgres", password="mysecretpassword", port=8000)
con = pg_con.cursor()

def run_script(con, filename):
    with open(filename, "r") as f:
        queries_file = f.read()
        queries = queries_file.split(";")
        for query in queries:
            if query.isspace():
                continue

            sql_statement = re.findall(r"^((CREATE|INSERT|DROP|DELETE|SELECT|COPY) [A-Za-z0-9_ ]*)", query, re.MULTILINE)
            print(f"{sql_statement[0][0].strip()} ...")
            start = time.time()
            con.execute(query)
            end = time.time()
            duration = end - start
            print(f"-> {duration:.4f} seconds")


run_script(con, "ddl/drop-tables.sql")
run_script(con, "ddl/schema-composite-merged-fk.sql")
run_script(con, "ddl/schema-delete-candidates.sql")

print("Load initial snapshot")

# initial snapshot
static_path = f"{data_dir}/initial_snapshot/static"
dynamic_path = f"{data_dir}/initial_snapshot/dynamic"
static_entities = ["Organisation", "Place", "Tag", "TagClass"]
dynamic_entities = ["Comment", "Comment_hasTag_Tag", "Forum", "Forum_hasMember_Person", "Forum_hasTag_Tag", "Person", "Person_hasInterest_Tag", "Person_knows_Person", "Person_likes_Comment", "Person_likes_Post", "Person_studyAt_University", "Person_workAt_Company", "Post", "Post_hasTag_Tag"]

if local:
    dbs_data_dir = data_dir
else:
    dbs_data_dir = '/data'

print("## Static entities")
for entity in static_entities:
    for csv_file in [f for f in os.listdir(f"{static_path}/{entity}") if f.startswith("part-") and f.endswith(".csv")]:
        csv_path = f"{entity}/{csv_file}"
        print(f"- {csv_path}")
        #print(f"- {csv_path}", end='\r')
        con.execute(f"COPY {entity} FROM '{dbs_data_dir}/initial_snapshot/static/{entity}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
        #print(" " * 120, end='\r')
        pg_con.commit()
print("Loaded static entities.")

print("## Dynamic entities")
for entity in dynamic_entities:
    for csv_file in [f for f in os.listdir(f"{dynamic_path}/{entity}") if f.startswith("part-") and f.endswith(".csv")]:
        csv_path = f"{entity}/{csv_file}"
        print(f"- {csv_path}")
        #print(f"- {csv_path}", end='\r')
        con.execute(f"COPY {entity} FROM '{dbs_data_dir}/initial_snapshot/dynamic/{entity}/{csv_file}' (DELIMITER '|', HEADER, FORMAT csv)")
        #print(" " * 120, end='\r')
        pg_con.commit()
print("Loaded dynamic entities.")

print("Creating materialized views . . . ")
run_script(con, "ddl/constraints.sql")
pg_con.commit()
print("Done.")

print("Loaded initial snapshot to Umbra.")
