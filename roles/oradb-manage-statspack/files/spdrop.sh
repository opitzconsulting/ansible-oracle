#!/usr/bin/bash
cd $HOME

${ORACLE_HOME}/bin/sqlplus -S -L /nolog <<EOF
conn / as sysdba

whenever oserror exit 1 rollback

@?/rdbms/admin/spdrop
exit
EOF