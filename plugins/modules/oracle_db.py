#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import time
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = '''
---
module: oracle_db
short_description: Manage an Oracle database
description:
    - Create/delete a database using dbca
    - If a responsefile is available, that will be used. If initparams is
      defined, those will be attached to the createDatabase command
    - If no responsefile is created, the database will be created based on all
      other parameters
version_added: "2.4.0"
options:
    oracle_home:
        description: >
            The home where the database will be created
        required: false
        type: str
        aliases: ['oh']
    db_name:
        description: The name of the database
        required: true
        default: None
        type: str
        aliases: ['db', 'database_name', 'name']
    sid:
        description: The instance name
        required: false
        type: str
        default: None
    db_unique_name:
        description: The database db_unique_name
        required: false
        default: None
        type: str
        aliases: ['dbunqn', 'unique_name']
    sys_password:
        description: Password for the sys user
        required: false
        default: None
        type: str
        aliases: ['syspw', 'sysdbapassword', 'sysdbapw']
    system_password:
        description: >
            Password for the system user.
            If not set, defaults to sys_password
        required: false
        type: str
        default: None
        aliases: ['systempw']
    dbsnmp_password:
        description: >
            Password for the dbsnmp user.
            If not set, defaults to sys_password
        required: false
        type: str
        default: None
        aliases: ['dbsnmppw']
    responsefile:
        description: The name of responsefile
        required: true
        type: str
        default: None
    template:
        description: >
            The template the database will be based off
        required: false
        type: str
        default: General_Purpose.dbc
    cdb:
        description: >
            Should the database be a container database
        required: false
        default: false
        type: str
        aliases: ['container']
        choices: ['True','False']
    datafile_dest:
        description: >
            Where the database files should be placed \
            (ASM diskgroup or filesystem path)
        required: false
        default: false
        type: str
        aliases: ['dfd']
    recoveryfile_dest:
        description: >
            Where the database files should be placed
            (ASM diskgroup or filesystem path)
        required: false
        default: false
        aliases: ['rfd']
    storage_type:
        description: >
            Type of underlying storage (Filesystem or ASM)
        required: false
        default: FS
        type: str
        aliases: ['storage']
        choices: ['FS', 'ASM']
    dbconfig_type:
        description: >
            Type of database (SI,RAC,RON)
        required: false
        type: str
        default: SI
        choices: ['SI', 'RAC', 'RACONENODE']
    db_type:
        description: >
            Default Type of database (MULTIPURPOSE, OLTP, DATA_WAREHOUSING)
        required: false
        type: str
        default: MULTIPURPOSE
        choices: ['MULTIPURPOSE', 'OLTP', 'DATA_WAREHOUSING']
    racone_service:
        description: >
            If dbconfig_type = RACONENODE, a service has to be created along
            with the DB. This is the name of that service
            If no name is defined, the service will be called
            "{{ db_name }}_ronserv"
        required: false
        type: str
        default: None
        aliases: ['ron_service']
    characterset:
        description: >
            The database characterset
        required: false
        type: str
        default: AL32UTF8
    memory_percentage:
        description: >
            The database total memory in % of available memory
        required: false
        type: str
    memory_totalmb:
        description: >
            The database total memory in MB. Defaults to 1G
        required: false
        type: str
        default: ['1024']
    nodelist:
        description: >
            The list of nodes a RAC DB should be created on
        required: false
        type: str
    amm:
        description: >
            Should Automatic Memory Management be used
            (memory_target, memory_max_target)
        required: false
        Default: false
        type: bool
        choices: ['true', 'false']
    omf:
        description: >
            Should Oracle Managed Files be used
        required: false
        Default: false
        type: bool
        choices: ['true', 'false']
    initparams:
        description: >
            List of dict for init.ora parameter.
        required: false
        type: list
        suboptions:
            name:
                description: The init.ora parameter name.
                type: str
            value:
                description: The parameter value.
                type: str
            scope:
                description: The scope of the parameter
                type: str
                default: both
                choices:
                    - "both"
                    - "spfile"
    customscripts:
        description: >
            List of scripts to run after database is created
        required: false
        type: list
    default_tablespace_type:
        description: >
            Database default tablespace type (DEFAULT_TBS_TYPE)
        required: false
        default: smallfile
        type: str
        choices: ['smallfile', 'bigfile']
    default_tablespace:
        description: >
            Database default tablespace
        default: smallfile
        required: false
        type: str
    default_temp_tablespace:
        description: >
            Database default temporary tablespace
        required: false
        type: str
    archivelog:
        description: >
            Puts the database is archivelog mode
        required: false
        default: false
        choices: ['true', 'false']
        type: bool
    force_logging:
        description: >
            Enables force logging for the Database
        required: False
        default: false
        choices: ['true', 'false']
        type: bool
    supplemental_logging:
        description: >
            Enables supplemental (minimal) logging for the Database
            (basically 'add supplemental log data')
        required: false
        default: false
        choices: ['true', 'false']
        type: bool
    flashback:
        description: >
            Enables flashback for the database
        required: False
        default: false
        choices: ['True', 'False']
        type: bool
    state:
        description: >
            The intended state of the database. For 'restarted' the database
            has to be running.
        default: present
        type: str
        choices: ['present', 'absent','started','restarted']
    force_restart:
        description: >
            Effective only when using state == 'restarted'
            If true (default), database will be restarted without checking \
            for spfile vs runtime parameters
            If false, database will ONLY be restarted if spfile is in use \
            and spfile parameters do not match runtime parameters
        required: false
        default: true
        choices: ['true', 'false']
        type: bool
        version_added: "3.8.0"
    hostname:
        description: >
            The host of the database if using dbms_service
        required: false
        type: str
        default: localhost
        aliases: ['host']
    port:
        description: >
            The listener port to connect to the database if using
            dbms_service
        required: false
        type: str
        default: 1521


notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Create a DB (non-cdb)
oracle_db:
    oh=/u01/app/oracle/12.2.0.1/db1
    db_name=orclcdb
    syspw=Oracle_123
    state=present
    storage=ASM
    dfd=+DATA
    rfd=+DATA
    default_tablespace_type: bigfile


- hosts: all
  gather_facts: true
  vars:
      oracle_home: /u01/app/oracle/12.2.0.1/db1
      dbname: orclcdb
      dbunqname: "{{ dbname}}_unq"
      container: True
      dbsid: "{{ dbname }}"
      hostname: "{{ ansible_hostname }}"
      oracle_env:
             ORACLE_HOME: "{{ oracle_home }}"
             LD_LIBRARY_PATH: "{{ oracle_home }}/lib"
      myaction: present
      rspfile: "/tmp/dbca_{{dbname}}.rsp"
      initparameters:
                - memory_target=0
                - memory_max_target=0
                - sga_target=1500M
                - sga_max_size=1500M
      dfd: +DATA
      rfd: +FRA
      storage: ASM
      dbtype: SI
      #ron_service: my_ron_service
      #clnodes: racnode-dc1-1,racnode-dc1-2
  tasks:
  - name: Manage database
    oracle_db:
           service_name={{ dbname }}
           hostname={{ hostname }}
           user=sys
           password=Oracle_123
           state={{ myaction }}
           db_name={{ dbname }}
           sid={{ dbsid | default(omit) }}
           db_unique_name={{ dbunqname | default(omit) }}
           sys_password=Oracle_123
           system_password=Oracle_123
           responsefile={{ rspfile | default(omit) }}
           cdb={{ container | default (omit) }}
           initparams={{ initparameters | default(omit) }}
           datafile_dest={{ dfd }}
           recoveryfile_dest={{ rfd }}
           storage_type={{ storage }}
           dbconfig_type={{ dbtype }}
           racone_service={{ ron_service | default(omit) }}
           amm=False
           memory_totalmb=1024
           nodelist={{ clnodes | default(omit) }}
    environment: "{{ oracle_env }}"
    run_once: True
'''


try:
    import cx_Oracle  # noqa E402
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True


def get_version(module, oracle_home):
    command = '%s/bin/sqlplus -V' % (oracle_home)
    (rc, stdout, stderr) = module.run_command(command)
    if rc != 0:
        msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, command)
        module.fail_json(msg=msg, changed=False)

    else:
        return stdout.split(' ')[2][0:4]


# Check if the database exists
def check_db_exists(module, oracle_home, db_name, sid, db_unique_name):
    global msg

    if sid is None:
        sid = ''
    if gimanaged:
        if db_unique_name is not None:
            checkdb = db_unique_name
        else:
            checkdb = db_name

        command = "%s/bin/srvctl config database -d %s " % (oracle_home, checkdb)
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            if 'PRCD-1229' in stdout:
                # DB created, with different ORACLE_HOME
                msg = 'Database %s already exists in a different home. Stdout -> %s' % (
                    db_name,
                    stdout,
                )
                module.fail_json(msg=msg, changed=False)

            elif '%s' % (db_name) in stdout:
                # <-- db doesn't exist
                return False

            else:
                msg = 'Error: command is %s. stdout is %s' % (command, stdout)
                return False

        elif 'Database name: %s' % (db_name) in stdout:
            # <-- Database already exist
            return True

        else:
            msg = '%s' % (stdout)
            return True

    else:
        existingdbs = []
        oratabfile = '/etc/oratab'
        if os.path.exists(oratabfile):
            with open(oratabfile) as oratab:
                for line in oratab:
                    if line.startswith('#') or line.startswith(' '):
                        continue

                    elif re.search(db_name + ':', line) or re.search(sid + ':', line):
                        existingdbs.append(line)

        if not existingdbs:
            # <-- db doesn't exist
            return False

        else:
            for dbs in existingdbs:
                if sid != '':
                    if '%s:' % db_name in dbs or '%s:' % sid in dbs:
                        if dbs.split(':')[1] != oracle_home.rstrip('/'):
                            # <-- DB created, but with a different ORACLE_HOME
                            msg = (
                                'Database %s already exists in a different '
                                'ORACLE_HOME (%s)' % (db_name, dbs.split(':')[1])
                            )
                            module.fail_json(msg=msg, changed=False)

                        elif dbs.split(':')[1] == oracle_home.rstrip('/'):
                            # <-- Database already exist
                            return True

                else:
                    if '%s:' % db_name in dbs:
                        if dbs.split(':')[1] != oracle_home.rstrip('/'):
                            # <-- DB created, but with a different ORACLE_HOME
                            msg = (
                                'Database %s already exists in a different '
                                'ORACLE_HOME (%s)' % (db_name, dbs.split(':')[1])
                            )
                            module.fail_json(msg=msg, changed=False)

                        elif dbs.split(':')[1] == oracle_home.rstrip('/'):
                            # <-- Database already exist
                            return True


def create_db(
    module,
    oracle_home,
    sys_password,
    system_password,
    dbsnmp_password,
    db_name,
    sid,
    db_unique_name,
    responsefile,
    template,
    cdb,
    local_undo,
    datafile_dest,
    recoveryfile_dest,
    storage_type,
    dbconfig_type,
    racone_service,
    characterset,
    memory_percentage,
    memory_totalmb,
    nodelist,
    db_type,
    amm,
    initparams,
    customscripts,
    datapatch,
    domain,
    omf,
):
    initparam = ' -initParams '
    paramslist = ''
    scriptlist = ''

    command = "%s/bin/dbca -createDatabase -silent " % (oracle_home)
    if responsefile is not None:
        if os.path.exists(responsefile):
            command += ' -responseFile %s ' % (responsefile)
        else:
            msg = 'Responsefile %s doesn\'t exist' % (responsefile)
            module.fail_json(msg=msg, changed=False)

        if db_unique_name is not None:
            initparam += 'db_name=%s,db_unique_name=%s,' % (db_name, db_unique_name)

        if domain is not None:
            initparam += 'db_domain=%s,' % domain

        if initparams is not None:
            paramslist = ",".join(initparams)
            initparam += '%s' % (paramslist)

        command += ' -gdbName %s' % (db_name)
        if sid is not None:
            command += ' -sid %s' % (sid)
        if sys_password is not None:
            command += ' -sysPassword \"%s\"' % (sys_password)
        if system_password is not None:
            command += ' -systemPassword \"%s\"' % (system_password)
        else:
            pw_found = False
            with open(responsefile) as rspfile:
                for line in rspfile:
                    if re.match('systemPassword=.+', line):
                        pw_found = True
                        break
            if not pw_found:
                command += ' -systemPassword \"%s\"' % (sys_password)
        if dbsnmp_password is not None:
            command += ' -dbsnmpPassword \"%s\"' % (dbsnmp_password)
        else:
            dbsnmp_password = sys_password
            command += ' -dbsnmpPassword \"%s\"' % (dbsnmp_password)
        if dbconfig_type == 'RAC':
            if nodelist is not None:
                nodelist = ",".join(nodelist)
                command += ' -nodelist %s ' % (nodelist)

    else:
        command += ' -gdbName %s' % (db_name)
        if sid is not None:
            command += ' -sid %s' % (sid)
        if sys_password is not None:
            command += ' -sysPassword \"%s\"' % (sys_password)
        if system_password is not None:
            command += ' -systemPassword \"%s\"' % (system_password)
        else:
            system_password = sys_password
            command += ' -systemPassword \"%s\"' % (system_password)
        if dbsnmp_password is not None:
            command += ' -dbsnmpPassword \"%s\"' % (dbsnmp_password)
        else:
            dbsnmp_password = sys_password
            command += ' -dbsnmpPassword \"%s\"' % (dbsnmp_password)
        if template:
            command += ' -templateName \"%s\"' % (template)
        if major_version > '11.2':
            if cdb is True:
                command += ' -createAsContainerDatabase true '
                if local_undo is True:
                    command += ' -useLocalUndoForPDBs true'
                else:
                    command += ' -useLocalUndoForPDBs false'
            else:
                command += ' -createAsContainerDatabase false '
        if datafile_dest is not None:
            command += ' -datafileDestination %s ' % (datafile_dest)
        if recoveryfile_dest is not None:
            command += ' -recoveryAreaDestination %s ' % (recoveryfile_dest)
        if storage_type is not None:
            command += ' -storageType %s ' % (storage_type)
        if dbconfig_type is not None:
            if dbconfig_type == 'SI':
                dbconfig_type = 'SINGLE'
            if major_version == '12.2':
                command += ' -databaseConfigType %s ' % (dbconfig_type)
            elif major_version == '12.1':
                command += ' -databaseConfType %s ' % (dbconfig_type)
        if dbconfig_type == 'RACONENODE':
            if racone_service is None:
                racone_service = db_name + '_ronserv'
            command += ' -RACOneNodeServiceName %s ' % (racone_service)
        if characterset is not None:
            command += ' -characterSet %s ' % (characterset)
        if memory_percentage is not None:
            command += ' -memoryPercentage %s ' % (memory_percentage)
        if memory_totalmb is not None:
            command += ' -totalMemory %s ' % (memory_totalmb)
        if dbconfig_type == 'RAC':
            if nodelist is not None:
                nodelist = ",".join(nodelist)
                command += ' -nodelist %s ' % (nodelist)
        if db_type is not None:
            command += ' -databaseType %s ' % (db_type)
        if amm is not None:
            if major_version == '12.2':
                if amm is True:
                    command += ' -memoryMgmtType AUTO '
                else:
                    command += ' -memoryMgmtType AUTO_SGA '
            elif major_version == '12.1':
                command += ' -automaticMemoryManagement %s ' % (str(amm).lower())

            elif major_version == '11.2':
                if amm is True:
                    command += ' -automaticMemoryManagement '

        if customscripts is not None:
            scriptlist = ",".join(customscripts)
            command += ' -customScripts %s ' % (scriptlist)

        if db_unique_name is not None:
            initparam += 'db_name=%s,db_unique_name=%s,' % (db_name, db_unique_name)

        if initparams is not None:
            # paramslist = ",".join(initparams)
            # initparam += ' %s' % (paramslist)
            initparam += ' %s' % (initparams)

    if omf is not None:
        if major_version >= '18.4':
            if omf is True:
                command += ' -useOMF true '
            else:
                command += ' -useOMF false '

    if initparam != ' -initParams ' or paramslist != "":
        command += initparam

    # msg = "command: %s" % (command)
    # module.fail_json(msg=msg, changed=False)
    (rc, stdout, stderr) = module.run_command(command)
    if rc != 0:
        msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, command)
        module.fail_json(msg=msg, changed=False)

    else:
        if output == 'short':
            return True

        else:
            verbosemsg = 'STDOUT: %s,  COMMAND: %s' % (stdout, command)
            verboselist.append(verbosemsg)
            return True, verboselist
            # module.exit_json(msg=verbosemsg, changed=True)

    # elif rc == 0 and datapatch:
    #     if run_datapatch(module, oracle_home, db_name, db_unique_name):
    #         return True
    # else:
    #     return True


def remove_db(module, oracle_home, db_name, sid, db_unique_name, sys_password):
    cursor = getconn(module)
    israc_sql = 'select parallel, instance_name, host_name from v$instance'
    israc_ = execute_sql_get(module, cursor, israc_sql)
    remove_db = ''
    if gimanaged:
        if db_unique_name is not None:
            remove_db = db_unique_name
        elif sid is not None and israc_[0][0] == 'YES':
            remove_db = db_name
        elif sid is not None and israc_[0][0] == 'NO':
            remove_db = sid
        else:
            remove_db = db_name
    else:
        if sid is not None:
            remove_db = sid
        else:
            remove_db = db_name

    command = (
        "%s/bin/dbca -deleteDatabase -silent -sourceDB %s -sysDBAUserName sys "
        "-sysDBAPassword %s" % (oracle_home, remove_db, sys_password)
    )
    (rc, stdout, stderr) = module.run_command(command)
    if rc != 0:
        msg = 'Removal of database %s failed: %s' % (db_name, stdout)
        module.fail_json(msg=msg, changed=False)

    else:
        if output == 'short':
            return True
        else:
            msg = 'STDOUT: %s,  COMMAND: %s' % (stdout, command)
            module.exit_json(msg=msg, changed=True)


def ensure_db_state(
    module,
    oracle_home,
    db_name,
    db_unique_name,
    sid,
    archivelog,
    force_logging,
    supplemental_logging,
    flashback,
    default_tablespace_type,
    default_tablespace,
    default_temp_tablespace,
    timezone,
):
    cursor = getconn(module)
    global israc
    slcomp = ''
    alterdb_sql = 'alter database'

    propsql = "select lower(property_value) from database_properties where \
        property_name in ('DEFAULT_TBS_TYPE', 'DEFAULT_PERMANENT_TABLESPACE', \
            'DEFAULT_TEMP_TABLESPACE') order by 1"
    tzsql = "select lower(property_value) from database_properties \
        where property_name = 'DBTIMEZONE'"

    curr_time_zone = execute_sql_get(module, cursor, tzsql)
    def_tbs_type, def_tbs, def_temp_tbs = execute_sql_get(module, cursor, propsql)
    israc_sql = 'select parallel, instance_name from v$instance'
    israc_ = execute_sql_get(module, cursor, israc_sql)
    instance_name = israc_[0][1]

    change_restart_sql = []
    change_db_sql = []
    log_check_sql = 'select log_mode, force_logging, flashback_on \
        from v$database'
    log_check_ = execute_sql_get(module, cursor, log_check_sql)

    if major_version >= '19.0':
        supp_log_check_sql = 'select SUPPLEMENTAL_LOG_DATA_MIN, \
            SUPPLEMENTAL_LOG_DATA_PL, SUPPLEMENTAL_LOG_DATA_SR, \
            SUPPLEMENTAL_LOG_DATA_PK, SUPPLEMENTAL_LOG_DATA_UI \
            from v$database'
        supp_log_check_ = execute_sql_get(module, cursor, supp_log_check_sql)
        if supp_log_check_[0][0] != slcomp:
            if supplemental_logging is True:
                slcomp = 'YES'
                slsql = alterdb_sql + ' add supplemental log data'
            else:
                slcomp = 'NO'
                slsql = alterdb_sql + ' drop supplemental log data'

            change_db_sql.append(slsql)

    if israc_[0][0] == 'NO':
        israc = False
    else:
        israc = True

    if archivelog is True:
        archcomp = 'ARCHIVELOG'
        archsql = alterdb_sql + ' archivelog'
    else:
        archcomp = 'NOARCHIVELOG'
        archsql = alterdb_sql + ' noarchivelog'

    if force_logging is True:
        flcomp = 'YES'
        flsql = alterdb_sql + ' force logging'
    else:
        flcomp = 'NO'
        flsql = alterdb_sql + ' no force logging'

    if flashback is True:
        fbcomp = 'YES'
        fbsql = alterdb_sql + ' flashback on'
    else:
        fbcomp = 'NO'
        fbsql = alterdb_sql + ' flashback off'

    if def_tbs_type[0] != default_tablespace_type:
        deftbstypesql = 'alter database set default %s tablespace ' % (
            default_tablespace_type
        )
        change_db_sql.append(deftbstypesql)

    if default_tablespace is not None and def_tbs[0] != default_tablespace:
        deftbssql = 'alter database default tablespace %s' % (default_tablespace)
        change_db_sql.append(deftbssql)

    if (
        default_temp_tablespace is not None
        and def_temp_tbs[0] != default_temp_tablespace
    ):
        deftempsql = 'alter database default temporary tablespace %s' % (
            default_temp_tablespace
        )
        change_db_sql.append(deftempsql)

    if timezone is not None and curr_time_zone[0][0] != timezone:
        deftzsql = 'alter database set time_zone = \'%s\'' % (timezone)
        change_db_sql.append(deftzsql)

    if log_check_[0][0] != archcomp:
        change_restart_sql.append(archsql)

    if log_check_[0][1] != flcomp:
        change_db_sql.append(flsql)

    if log_check_[0][2] != fbcomp:
        change_db_sql.append(fbsql)

    if len(change_db_sql) > 0 or len(change_restart_sql) > 0:
        if (
            log_check_[0][0] == 'ARCHIVELOG'
            and log_check_[0][2] == 'YES'
            and not archivelog
            and not flashback
        ):
            # Flashback database needs to be turned off before
            # archivelog is turned off
            # todo: This is not needed anymore!

            if len(change_db_sql) > 0:
                # <- Apply changes that does not require a restart
                apply_norestart_changes(module, change_db_sql)

            if len(change_restart_sql) > 0:
                # Apply changes that requires a restart
                apply_restart_changes(
                    module,
                    oracle_home,
                    db_name,
                    db_unique_name,
                    sid,
                    instance_name,
                    israc,
                    change_restart_sql,
                )
        else:
            if len(change_restart_sql) > 0:
                # <- Apply changes that requires a restart
                apply_restart_changes(
                    module,
                    oracle_home,
                    db_name,
                    db_unique_name,
                    sid,
                    instance_name,
                    israc,
                    change_restart_sql,
                )

            if len(change_db_sql) > 0:
                # Apply changes that does not require a restart
                apply_norestart_changes(module, change_db_sql)

        msg = (
            'Database %s has been put in the intended state - Archivelog: %s, '
            'Force Logging: %s, Flashback: %s, Supplemental Logging: %s, '
            'Timezone: %s'
            % (
                db_name,
                archivelog,
                force_logging,
                flashback,
                supplemental_logging,
                timezone,
            )
        )

        module.exit_json(msg=msg, changed=True)
    else:
        if newdb:
            msg = 'Database %s successfully created created (%s) ' % (db_name, archcomp)
            if output == 'verbose':
                msg += ' ,'.join(verboselist)
            changed = True
        else:
            msg = (
                'Database %s already exists and is in the intended state - '
                'Archivelog: %s, Force Logging: %s, Flashback: %s, Supplemental '
                'Logging: %s, Timezone: %s'
                % (
                    db_name,
                    archivelog,
                    force_logging,
                    flashback,
                    supplemental_logging,
                    timezone,
                )
            )
            changed = False
        module.exit_json(msg=msg, changed=changed)


def apply_restart_changes(
    module,
    oracle_home,
    db_name,
    db_unique_name,
    sid,
    instance_name,
    israc,
    change_restart_sql,
):
    open_mode = stop_db(module, oracle_home, db_name, db_unique_name, sid)
    start_instance(
        module, oracle_home, db_name, db_unique_name, sid, 'mount', israc, instance_name
    )
    cursor = getconn(module)
    for sql in change_restart_sql:
        execute_sql(module, cursor, sql)
    stop_db(module, oracle_home, db_name, db_unique_name, sid)
    start_db(module, oracle_home, db_name, db_unique_name, sid, open_mode)


def apply_norestart_changes(module, change_db_sql):
    cursor = getconn(module)
    for sql in change_db_sql:
        execute_sql(module, cursor, sql)


def spfile_restart_needed(module, force_restart):
    if force_restart:
        return True, ['force_restart option was given']
    cursor = getconn(module)
    init_parameter_sql = 'SELECT DECODE(value, NULL, \
          \'PFILE\', \'SPFILE\') "Init File Type" \
          FROM sys.v$parameter WHERE name = \'spfile\''
    init_parameter_style = execute_sql_get(module, cursor, init_parameter_sql)
    if init_parameter_style[0][0] == 'PFILE':
        # no restart needed if running with PFILE
        return False, ['database running without spfile and force_restart is false']

    if major_version > '11.2':
        spf_check_sql = (
            "select vsp.name || ':' || vp.value || ' -> ' || "
            "vsp.value as change from "
            "( select name, listagg(value,', ') within group "
            "(order by value) as value, con_id from v$spparameter"
            "  group by name, con_id) vsp, "
            "( select name, listagg(value,', ') within group "
            "(order by value) as value, con_id from v$parameter2 "
            " group by name, con_id) vp "
            "where vsp.name=vp.name "
            "and vsp.con_id = vp.con_id "
            "and upper(vsp.value) != upper(vp.value)"
        )
    else:
        spf_check_sql = (
            "select vsp.name || ':' || vp.value || ' -> ' || "
            "vsp.value as change from "
            "( select name, listagg(value,', ') within group "
            "(order by value) as value from v$spparameter "
            "group by name) vsp, "
            "( select name, listagg(value,', ') within group "
            "(order by value) as value from v$parameter2 "
            "group by name) vp "
            "where vsp.name=vp.name and upper(vsp.value) != upper(vp.value)"
        )

    init_changes = execute_sql_get(module, cursor, spf_check_sql)
    if len(init_changes) == 0:
        return False, ['spfile parameters match runtime']
    else:
        return True, [i[0] for i in init_changes]


def stop_db(module, oracle_home, db_name, db_unique_name, sid):
    # global debug
    # debug.append('stop_db called')

    if gimanaged:
        if db_unique_name is not None:
            db_name = db_unique_name
        command = '%s/bin/srvctl stop database -d %s -o immediate' % (
            oracle_home,
            db_name,
        )
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            msg = 'Error(stop_db) - STDOUT: %s, STDERR: %s, COMMAND: %s' % (
                stdout,
                stderr,
                command,
            )
            module.fail_json(msg=msg, changed=False)

        else:
            # Grid knows the right open mode, so return None to be passed to
            # start_instance
            return None

    else:
        # query current open_mode for potential restart in case of non-grid
        cursor = getconn(module)
        open_mode_sql = (
            "SELECT CASE OPEN_MODE WHEN 'MOUNTED' "
            "THEN 'mount' "
            "WHEN 'READ WRITE' THEN 'open read write' "
            "ELSE 'open read only' END AS open_mode FROM V$DATABASE"
        )
        open_mode = execute_sql_get(module, cursor, open_mode_sql)

        if sid is not None:
            os.environ['ORACLE_SID'] = sid
        else:
            os.environ['ORACLE_SID'] = db_name
        shutdown_sql = '''
        connect / as sysdba
        shutdown immediate;
        exit
        '''
        sqlplus_bin = '%s/bin/sqlplus' % (oracle_home)
        p = subprocess.Popen(
            [sqlplus_bin, '/nolog'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (stdout, stderr) = p.communicate(shutdown_sql.encode('utf-8'))
        rc = p.returncode
        # debug.append('stop_db: rc=%d, STDOUT: %s, STDERR: %s, COMMAND: %s' %
        #              (rc, stdout, stderr, shutdown_sql))
        # debug.append('stop_db env: USER:%s ORACLE_HOME:%s ORACLE_SID:%s' %
        #              (os.environ['USER'], os.environ['ORACLE_SID'],
        #               os.environ['ORACLE_HOME']))
        if rc != 0 or (b'ORA-' in stdout and b'ORA-01109:' not in stdout):
            msg = 'Error(stop_db) - STDOUT: %s, STDERR: %s, COMMAND: %s' % (
                stdout,
                stderr,
                shutdown_sql,
            )
            # module.fail_json(msg=msg, changed=False, debug=debug)
            module.fail_json(msg=msg, changed=False)
        else:
            # return previous open_mode in format suitable for startup command
            return open_mode[0][0]


def start_db(module, oracle_home, db_name, db_unique_name, sid, open_mode=None):
    # global debug
    # debug.append('start_db called with open_mode %s,
    #              calling start_instance' % \
    #              (open_mode or "None"))
    return start_instance(
        module, oracle_home, db_name, db_unique_name, sid, open_mode, False, ''
    )


def start_instance(
    module,
    oracle_home,
    db_name,
    db_unique_name,
    sid,
    open_mode=None,
    israc=False,
    instance_name='',
):
    # global debug
    # debug.append('start_instance called with open_mode %s' % (open_mode or "None"))  # noqa E501

    if gimanaged:
        if db_unique_name is not None:
            db_name = db_unique_name

        if israc:
            command = '%s/bin/srvctl status instance -d %s -i %s' % (
                oracle_home,
                db_name,
                instance_name,
            )
        else:
            command = '%s/bin/srvctl status database -d %s ' % (oracle_home, db_name)

        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            msg = 'Error(start_instance) - STDOUT: %s, STDERR: %s, COMMAND: %s' % (
                stdout,
                stderr,
                command,
            )  # noqa E501
            module.fail_json(msg=msg, changed=False)

        elif 'is running' in stdout:
            return 'ok'

        elif 'is not running' in stdout:
            if israc:
                command = '%s/bin/srvctl start instance -d %s -i %s' % (
                    oracle_home,
                    db_name,
                    instance_name,
                )
            else:
                command = '%s/bin/srvctl start database -d %s ' % (oracle_home, db_name)
            if open_mode is not None:
                command += ' -o %s ' % (open_mode)
            (rc, stdout, stderr) = module.run_command(command)

            # To allow the DB to register with the listener,
            # as following tasks may want to connect to it immediately and fail
            time.sleep(10)

            if rc != 0:
                msg = (
                    'Error(start_instance) - STDOUT: %s, STDERR: %s, '
                    'COMMAND: %s' % (stdout, stderr, command)
                )
                module.fail_json(msg=msg, changed=False)
            else:
                return 'changed'
        else:
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (
                stdout,
                stderr,
                command,
            )
            module.fail_json(msg=msg, changed=False)

    else:
        if sid is not None:
            os.environ['ORACLE_SID'] = sid
        else:
            os.environ['ORACLE_SID'] = db_name

        startup_sql = '''
        connect / as sysdba
        startup %s;
        exit
        ''' % (
            open_mode or ""
        )
        sqlplus_bin = '%s/bin/sqlplus' % (oracle_home)
        p = subprocess.Popen(
            [sqlplus_bin, '/nolog'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (stdout, stderr) = p.communicate(startup_sql.encode('utf-8'))
        rc = p.returncode

        # To allow the DB to register with the listener,
        # as following tasks may want to connect to it immediately and fail
        time.sleep(10)

        # debug.append('start_instance: rc=%d, Error - STDOUT: %s, ' \
        #              'STDERR: %s, COMMAND: %s' % \
        #              (rc, stdout, stderr, startup_sql))
        # debug.append('start_instance: env: USER:%s ORACLE_HOME:%s ' \
        #              'ORACLE_SID:%s' % (os.environ['USER'],
        #                                 os.environ['ORACLE_SID'],
        #                                 os.environ['ORACLE_HOME']))
        if b'ORA-01081:' in stdout:
            return 'ok'
        elif rc != 0 or b'ORA-' in stdout:
            msg = 'Error(start_instance) - STDOUT: %s, STDERR: %s, COMMAND: %s' % (
                stdout,
                stderr,
                startup_sql,
            )
            # module.fail_json(msg=msg, changed=False, debug=debug)
            module.fail_json(msg=msg, changed=False)
        else:
            return 'changed'


def execute_sql_get(module, cursor, sql):
    try:
        cursor.execute(sql)
        result = cursor.fetchall()
    except cx_Oracle.DatabaseError as exc:
        (error,) = exc.args
        msg = 'Something went wrong while executing sql_get - %s sql: %s' % (
            error.message,
            sql,
        )
        module.fail_json(msg=msg, changed=False)
    return result


def execute_sql(module, cursor, sql):
    try:
        cursor.execute(sql)
    except cx_Oracle.DatabaseError as exc:
        (error,) = exc.args
        msg = 'Something went wrong while executing sql - %s sql: %s' % (
            error.message,
            sql,
        )
        module.fail_json(msg=msg, changed=False)
    return True


def getconn(module):
    hostname = os.uname()[1]
    wallet_connect = '/@%s' % service_name
    try:
        if not user and not password:
            # If neither user or password is supplied, the use of an
            # oracle wallet is assumed
            connect = wallet_connect
            conn = cx_Oracle.connect(wallet_connect, mode=cx_Oracle.SYSDBA)

        elif user and password:
            dsn = cx_Oracle.makedsn(host=hostname, port=port, service_name=service_name)
            connect = dsn
            conn = cx_Oracle.connect(user, password, dsn, mode=cx_Oracle.SYSDBA)

        elif not user or not password:
            module.fail_json(msg='Missing username or password for cx_Oracle')

    except cx_Oracle.DatabaseError as exc:
        (error,) = exc.args
        msg = 'Could not connect to database - %s, connect descriptor: %s' % (
            error.message,
            connect,
        )
        module.fail_json(msg=msg, changed=False)

    cursor = conn.cursor()
    return cursor


def main():
    global msg
    global gimanaged
    global major_version
    global user
    global password
    global service_name
    global hostname
    global port
    global israc
    global newdb
    global output
    global verbosemsg
    global verboselist
    global domain
    global cursor

    cursor = None

    # global debug
    verbosemsg = ''
    verboselist = []
    # debug = []
    newdb = False

    # fmt: off
    module = AnsibleModule(
        argument_spec=dict(
            oracle_home         = dict(default=None, aliases = ['oh']), # noqa E231
            db_name             = dict(required=True, aliases = ['db', 'database_name', 'name']), # noqa E231
            sid                 = dict(required=False), # noqa E231
            db_unique_name      = dict(required=False, aliases = ['dbunqn','unique_name']), # noqa E231
            sys_password        = dict(required=False, no_log=True, aliases = ['syspw', 'sysdbapassword', 'sysdbapw']), # noqa E231
            system_password     = dict(required=False, no_log=True, aliases = ['systempw']), # noqa E231
            dbsnmp_password     = dict(required=False, no_log=True, aliases = ['dbsnmppw']), # noqa E231
            responsefile        = dict(required=False), # noqa E231
            template            = dict(default='General_Purpose.dbc'), # noqa E231
            cdb                 = dict(default=False, type='bool', aliases=['container']), # noqa E231
            local_undo          = dict(default=True, type='bool'), # noqa E231
            datafile_dest       = dict(required=False, aliases= ['dfd']), # noqa E231
            recoveryfile_dest   = dict(required=False, aliases= ['rfd']), # noqa E231
            storage_type        = dict(default='FS', aliases= ['storage'], choices = ['FS','ASM']), # noqa E231
            dbconfig_type       = dict(default='SI', choices = ['SI', 'RAC', 'RACONENODE']), # noqa E231
            db_type             = dict(default='MULTIPURPOSE', choices = ['MULTIPURPOSE', 'DATA_WAREHOUSING', 'OLTP']), # noqa E231
            racone_service      = dict(required=False, aliases = ['ron_service']), # noqa E231
            characterset        = dict(default='AL32UTF8'), # noqa E231
            memory_percentage   = dict(required=False), # noqa E231
            memory_totalmb      = dict(default='1024'), # noqa E231
            nodelist            = dict(required=False, type='list'), # noqa E231
            amm                 = dict(default=False, type='bool', aliases = ['automatic_memory_management']), # noqa E231
            initparams          = dict(required=False, type='list'), # noqa E231
            force_restart       = dict(default=True, type='bool'), # noqa E231
            customscripts       = dict(required=False, type='list'), # noqa E231
            default_tablespace_type = dict(default='smallfile', choices = ['smallfile', 'bigfile']), # noqa E231
            default_tablespace  = dict(required=False), # noqa E231
            default_temp_tablespace  = dict(required=False), # noqa E231
            archivelog          = dict(default=False, type='bool'), # noqa E231
            force_logging       = dict(default=False, type='bool'), # noqa E231
            supplemental_logging       = dict(default=False, type='bool'), # noqa E231
            flashback           = dict(default=False, type='bool'), # noqa E231
            datapatch           = dict(default=True, type='bool'), # noqa E231
            domain              = dict(required=False), # noqa E231
            timezone            = dict(required=False), # noqa E231
            output              = dict(default="short", choices = ["short", "verbose"]), # noqa E231
            state               = dict(default="present", choices = ["present", "absent", "started", "restarted"]), # noqa E231
            hostname            = dict(required=False, default = 'localhost', aliases = ['host']), # noqa E231
            port                = dict(required=False, default = 1521), # noqa E231
            omf                 = dict(required=False, type='bool', default=False), #noqa E231
        ),
        mutually_exclusive=[['memory_percentage', 'memory_totalmb']],
    )
    # fmt: on

    # fmt: off
    oracle_home         = module.params["oracle_home"] # noqa E221
    db_name             = module.params["db_name"] # noqa E221
    sid                 = module.params["sid"] # noqa E221
    db_unique_name      = module.params["db_unique_name"] # noqa E221
    sys_password        = module.params["sys_password"] # noqa E221
    system_password     = module.params["system_password"] # noqa E221
    dbsnmp_password     = module.params["dbsnmp_password"] # noqa E221
    responsefile        = module.params["responsefile"] # noqa E221
    template            = module.params["template"] # noqa E221
    cdb                 = module.params["cdb"] # noqa E221
    local_undo          = module.params["local_undo"] # noqa E221
    datafile_dest       = module.params["datafile_dest"] # noqa E221
    recoveryfile_dest   = module.params["recoveryfile_dest"] # noqa E221
    storage_type        = module.params["storage_type"] # noqa E221
    dbconfig_type       = module.params["dbconfig_type"] # noqa E221
    racone_service      = module.params["racone_service"] # noqa E221
    characterset        = module.params["characterset"] # noqa E221
    memory_percentage   = module.params["memory_percentage"] # noqa E221
    memory_totalmb      = module.params["memory_totalmb"] # noqa E221
    nodelist            = module.params["nodelist"] # noqa E221
    db_type             = module.params["db_type"] # noqa E221
    amm                 = module.params["amm"] # noqa E221
    initparams          = module.params["initparams"] # noqa E221
    force_restart       = module.params["force_restart"] # noqa E231
    customscripts       = module.params["customscripts"] # noqa E221
    default_tablespace_type = module.params["default_tablespace_type"] # noqa E221
    default_tablespace      = module.params["default_tablespace"] # noqa E221
    default_temp_tablespace = module.params["default_temp_tablespace"] # noqa E221
    archivelog          = module.params["archivelog"] # noqa E221
    force_logging       = module.params["force_logging"] # noqa E221
    supplemental_logging    = module.params["supplemental_logging"] # noqa E221
    flashback           = module.params["flashback"] # noqa E221
    datapatch           = module.params["datapatch"] # noqa E221
    domain              = module.params["domain"] # noqa E221
    timezone            = module.params["timezone"] # noqa E221
    output              = module.params["output"] # noqa E221
    state               = module.params["state"] # noqa E221
    hostname            = module.params["hostname"] # noqa E221
    port                = module.params["port"] # noqa E221
    omf                 = module.params["omf"] # noqa E221
    # fmt: on

    # ld_library_path = '%s/lib' % (oracle_home)
    if oracle_home is not None:
        os.environ['ORACLE_HOME'] = oracle_home.rstrip('/')
        # os.environ['LD_LIBRARY_PATH'] = ld_library_path
    elif 'ORACLE_HOME' in os.environ:
        oracle_home = os.environ['ORACLE_HOME']
        # ld_library_path = os.environ['LD_LIBRARY_PATH']
    else:
        msg = 'ORACLE_HOME variable not set. Please set it and re-run the command'  # noqa E501
        module.fail_json(msg=msg, changed=False)

    if not cx_oracle_exists:
        msg = "The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH is set"  # noqa E501
        module.fail_json(msg=msg)

    # Decide whether to use srvctl or sqlplus
    if os.path.exists('/etc/oracle/olr.loc'):
        gimanaged = True
    else:
        gimanaged = False
        if not cx_oracle_exists:
            msg = "The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH are set"  # noqa E501
            module.fail_json(msg=msg)

    # Connection details for database
    user = 'sys'
    password = sys_password
    if db_unique_name is not None:
        service_name = db_unique_name
    else:
        service_name = db_name

    if domain is not None and domain != '':
        service_name = "%s.%s" % (service_name, domain)

    # Get the Oracle version
    major_version = get_version(module, oracle_home)

    if state == 'started' or state == 'restarted':
        msg = "oracle_home: %s db_name: %s sid: %s db_unique_name: %s" % (
            oracle_home,
            db_name,
            sid,
            db_unique_name,
        )
        spf_restart_needed = False

        if not check_db_exists(module, oracle_home, db_name, sid, db_unique_name):
            msg = "Database not found. %s" % msg
            module.fail_json(msg=msg, changed=False)

        else:
            if state == 'restarted':
                spf_restart_needed, spf_restart_reason = spfile_restart_needed(
                    module, force_restart
                )

                if spf_restart_needed:
                    open_mode = stop_db(
                        module, oracle_home, db_name, db_unique_name, sid
                    )

                else:
                    # ensure db runs (in default open mode) if not restarting
                    open_mode = None

                start_db_state = start_db(
                    module, oracle_home, db_name, db_unique_name, sid, open_mode
                )
            else:
                start_db_state = start_db(
                    module, oracle_home, db_name, db_unique_name, sid
                )

            if start_db_state == 'changed' and not spf_restart_needed:
                msg = "Database started."
                # module.exit_json(msg=msg, changed=True, debug=debug)
                module.exit_json(msg=msg, changed=True)
            elif start_db_state == 'changed':
                msg = "Database restarted."
                # module.exit_json(msg=msg, restart_reason=spf_restart_reason,
                # changed=True, debug=debug)
                module.exit_json(
                    msg=msg, restart_reason=spf_restart_reason, changed=True
                )
            elif start_db_state == 'ok' and state == 'restarted':
                msg = "No restart needed (%s)" % (spf_restart_reason[0])
                module.exit_json(msg=msg, changed=False)
            elif start_db_state == 'ok':
                msg = "Database already running."
                module.exit_json(msg=msg, changed=False)
            else:
                msg = "Startup failed. %s" % msg
                module.fail_json(msg=msg, changed=False)

    elif state == 'present':
        if not check_db_exists(module, oracle_home, db_name, sid, db_unique_name):
            if create_db(
                module,
                oracle_home,
                sys_password,
                system_password,
                dbsnmp_password,
                db_name,
                sid,
                db_unique_name,
                responsefile,
                template,
                cdb,
                local_undo,
                datafile_dest,
                recoveryfile_dest,
                storage_type,
                dbconfig_type,
                racone_service,
                characterset,
                memory_percentage,
                memory_totalmb,
                nodelist,
                db_type,
                amm,
                initparams,
                customscripts,
                datapatch,
                domain,
                omf,
            ):
                newdb = True
                ensure_db_state(
                    module,
                    oracle_home,
                    db_name,
                    db_unique_name,
                    sid,
                    archivelog,
                    force_logging,
                    supplemental_logging,
                    flashback,
                    default_tablespace_type,
                    default_tablespace,
                    default_temp_tablespace,
                    timezone,
                )

            else:
                module.fail_json(msg=msg, changed=False)
        else:
            ensure_db_state(
                module,
                oracle_home,
                db_name,
                db_unique_name,
                sid,
                archivelog,
                force_logging,
                supplemental_logging,
                flashback,
                default_tablespace_type,
                default_tablespace,
                default_temp_tablespace,
                timezone,
            )
            # msg = 'Database %s already exists' % (db_name)
            # module.exit_json(msg=msg, changed=False)

    elif state == 'absent':
        if check_db_exists(module, oracle_home, db_name, sid, db_unique_name):
            if remove_db(
                module, oracle_home, db_name, sid, db_unique_name, sys_password
            ):
                msg = 'Successfully removed database %s' % (db_name)
                module.exit_json(msg=msg, changed=True)
            else:
                module.fail_json(msg=msg, changed=False)
        else:
            msg = 'Database %s doesn\'t exist' % (db_name)
            module.exit_json(msg=msg, changed=False)

    module.exit_json(msg="Unhandled exit", changed=False)


if __name__ == '__main__':
    main()
