#!/usr/bin/bash
cd $HOME

${ORACLE_HOME}/bin/sqlplus -S -L /nolog <<EOF
conn / as sysdba

define perfstat_password=${perfstat_password}
define temporary_tablespace=${temporary_tablespace}
define default_tablespace=${default_tablespace}
define purgedates=${purgedates}
define snaplevel=${snaplevel}

whenever sqlerror exit 1 rollback
@?/rdbms/admin/spcreate

set echo on
alter session set current_schema=perfstat;

-- Re-fill STATS\$IDLE_EVENT with latest idle events that Oracle regularly forgets to update.
delete from perfstat.STATS\$IDLE_EVENT;
insert into perfstat.STATS\$IDLE_EVENT select name from V\$EVENT_NAME where wait_class='Idle';
commit;

create index perfstat.STATS\$SQLTEXT_UK1 on STATS\$SQLTEXT(sql_id, piece);

exit
EOF