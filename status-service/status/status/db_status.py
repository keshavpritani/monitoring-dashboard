from status.essentials import *
from datetime import datetime
from django.db import connections

sessions = {}

def db_session_check():
    logger.info("Checking DB session and uptime")
    databases = ['vpn2']
    SESSION_LIMIT = int(get_property("SESSION_LIMIT"))
    AVG_SESSION_COUNT = int(get_property("AVG_SESSION_COUNT"))
    LONG_QUERY_THRESHOLD = int(get_property("LONG_QUERY_THRESHOLD"))
    if ENV == "prod":
        databases.append('kyc')
    if ENV not in ("dev", "local"): databases.append('reports')
    try:
        for db in databases:
            sessions.setdefault(db, [])
            cursor = connections[f"{db}-writer"].cursor()
            logger.info("Checking DB session for {}".format(db))

            postgreSQL_select_Query = "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' and query not like '%pg_stat_activity WHERE state%';"
            postgreSQL_select_uptime_Query = "SELECT pg_postmaster_start_time();"
            cursor.execute(postgreSQL_select_Query)
            db_session = cursor.fetchone()[0]
            cursor.execute(postgreSQL_select_uptime_Query)
            uptime = cursor.fetchone()[0]
            uptime = uptime.replace(tzinfo=None)
            sessions[db].append(db_session)
            average_session = 0
            if len(sessions[db]) >= AVG_SESSION_COUNT: 
                average_session = round(sum(sessions[db]) / len(sessions[db]), 2)
                sessions[db].pop(0)
            logger.info(f"DB {db} session: {average_session}")
            if average_session > SESSION_LIMIT:
                if ENV == "prod": send_exection_alert(f"DB {db} session: {average_session}")
                else: send_alert(f"{db}-sessions", "Red", "db",
                           f", {average_session} active sessions")
            delta = datetime.now()-uptime
            if delta.total_seconds() < (10*60):
                send_alert(f"{db}-uptime", "Red", "db",
                           f", uptime is {delta}")
            postgreSQL_select_Query = f"SELECT user, datname, now() - query_start AS query_time, query FROM pg_stat_activity WHERE state = 'active' and query not like '%START_REPLICATION%' and query not like '%autovacuum:%' and (now() - query_start) >= interval '{LONG_QUERY_THRESHOLD} Minutes';"
            cursor.execute(postgreSQL_select_Query)
            long_queries = cursor.fetchall()
            if len(long_queries) > 0:
                msg = f"\nQueries that took longer than {LONG_QUERY_THRESHOLD} minutes:\n"
                for query in long_queries:
                    msg += f"Database - {query[1]} took {query[2]}, query: {query[3][:200]}\n"
                if ENV == "prod": send_exection_alert(f"{db}-long-queries {msg}")
                else: send_alert(f"{db}-long-queries", "Yellow", "db", msg)
            cursor.close()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while checking DB session and uptime")
