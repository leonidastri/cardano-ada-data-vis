from django.db import connection

def execute_view_query(sql_query):
    with connection.cursor() as cursor:
        cursor.execute(sql_query)

def execute_query(sql_query):
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        return dictfetchall(cursor)

def execute_query_params(sql_query, params):
    with connection.cursor() as cursor:
        cursor.execute(sql_query,params)
        return dictfetchall(cursor)

def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]