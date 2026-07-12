pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  from pkg_resources import DistributionNotFound, get_distribution
Traceback (most recent call last):
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
    ~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/base.py", line 256, in get_new_connection
    connection = Database.connect(**conn_params)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 361, in __init__
    self.connect()
    ~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 669, in connect
    self._request_authentication()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 979, in _request_authentication
    auth_packet = _auth.caching_sha2_password_auth(self, auth_packet)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/_auth.py", line 241, in caching_sha2_password_auth
    pkt = conn._read_packet()
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 775, in _read_packet
    packet.raise_for_error()
    ~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/protocol.py", line 219, in raise_for_error
    err.raise_mysql_exception(self._data)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/err.py",line 150, in raise_mysql_exception
    raise errorclass(errno, errval)
pymysql.err.OperationalError: (1049, "Unknown database 'iwmsdbgovernment'")

The above exception was the direct cause of the followingexception:

Traceback (most recent call last):
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/manage.py", line 22, in <module>
    main()
    ~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/manage.py", line 18, in main
    execute_from_command_line(sys.argv)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
    ~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/management/base.py", line 416, in run_from_argv
    self.execute(*args, **cmd_options)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/management/base.py", line 457, in execute
    self.check(**check_kwargs)
    ~~~~~~~~~~^^^^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/management/base.py", line 492, in check
    all_issues = checks.run_checks(
        app_configs=app_configs,
    ...<2 lines>...
        databases=databases,
    )
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/checks/registry.py", line 89, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/core/checks/database.py", line 13, in check_database_backends
    issues.extend(conn.validation.check(**kwargs))
                  ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/validation.py", line 9, in check
    issues.extend(self._check_sql_mode(**kwargs))
                  ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/validation.py", line 14, in _check_sql_mode
    self.connection.sql_mode & {"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}
    ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ~~~~~~~~~^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/base.py", line 448, in sql_mode
    sql_mode = self.mysql_server_data["sql_mode"]
               ^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ~~~~~~~~~^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/base.py", line 404, in mysql_server_data
    with self.temporary_connection() as cursor:
         ~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py", line 141, in __enter__
    return next(self.gen)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 695, in temporary_connection
    with self.cursor() as cursor:
         ~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 320, in cursor
    return self._cursor()
           ~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 296, in _cursor
    self.ensure_connection()
    ~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 278, in ensure_connection
    with self.wrap_database_errors:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/utils.py", line 91, in __exit__
    raise dj_exc_value.with_traceback(traceback) from exc_value
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
    ~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/django/db/backends/mysql/base.py", line 256, in get_new_connection
    connection = Database.connect(**conn_params)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 361, in __init__
    self.connect()
    ~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 669, in connect
    self._request_authentication()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 979, in _request_authentication
    auth_packet = _auth.caching_sha2_password_auth(self, auth_packet)
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/_auth.py", line 241, in caching_sha2_password_auth
    pkt = conn._read_packet()
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/connections.py", line 775, in _read_packet
    packet.raise_for_error()
    ~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/protocol.py", line 219, in raise_for_error
    err.raise_mysql_exception(self._data)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/zigma-mac/Documents/IWMS/iwms-government-backend/.venv/lib/python3.14/site-packages/pymysql/err.py",line 150, in raise_mysql_exception
    raise errorclass(errno, errval)
django.db.utils.OperationalError: (1049, "Unknown database 'iwmsdbgovernment'")
(iwms-government-backend) ➜  iwms-government-backend git:(sameer) 