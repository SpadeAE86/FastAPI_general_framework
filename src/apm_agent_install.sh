#!/bin/bash
function help()
{
#usage
cat << HELP
Usage  : please switch to root account in order to run this script.
Options:
    ak          : access key
    sk          : security key
    code        : aom access code
    region      : region in xxxx
    projectid   : project id in iam
    obsdomain   : the obs domain, default value is xxx domain
    accessip    : the elb ip addr
    plugoff     : the plugin need to disable, eg: log
Example:
    bash apm_agent_install.sh -accessip 192.168.0.1 -accessdomain xxx;
    bash apm_agent_install.sh -accessip 192.168.0.1 -accessdomain xxx -obsdomain domain obs.xxxx.xxx;
    bash apm_agent_install.sh -ak master -sk master -region xxxx -projectid master
    bash apm_agent_install.sh -ak sdd8268daw8 -sk asdfdpkmd89s -projectid 78ssssffff8963s -region xxxx;
    bash apm_agent_install.sh -ak sdd8268daw8 -sk asdfdpkmd89s -projectid 78ssssffff8963s -region xxxx -accessip 192.168.0.1 -accessdomain xxx -obsdomain obs.xxxx.xxx;
    bash apm_agent_install.sh -code asdfdpkmd89s -projectid 78ssssffff8963s -region cn-north-1 -accessip 192.168.0.1 -accessdomain xxx -obsdomain obs.xxxx.xxx;
    bash apm_agent_install.sh -ak sdd8268daw8 -sk asdfdpkmd89s -projectid 78ssssffff8963s -region xxxx -plugoff log;
    bash apm_agent_install.sh -scene internet -ak sdd8268daw8 -sk asdfdpkmd89s -projectid 78ssssffff8963s -accessip 192.168.0.1 -accessdomain xxx;
    bash apm_agent_install.sh -aomaksk sdsgddfds -ltsaksk dsdsdsds -projectid 78ssssffff8963s -region xxxx;
HELP
exit 1
}

function logError() {
    DATE_N=`date "+%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo -e "\e[1;41m${DATE_N} [ERROR]\e[0m : $@";
}

function logInfo() {
    DATE_N=`date "+%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo -e "\033[32m${DATE_N} [INFO]\033[0m : $@"
}

function checkUser()
{
    if [ "root" != "${CURRENT_USER}" ]
    then
        echo "please switch to root account in order to run this script."
        help
        exit 1
    fi
}

function checkOption()
{
    key=$1
    if [ "$key" = "-ak" -o "$key" = "-sk" -o "$key" = "-region" -o "$key" = "-projectid" \
            -o "$key" = "-obsdomain" -o "$key" = "-accessip" -o "$key" = "-scene" \
            -o "$key" = "-dc" -o "$key" = "-plugoff" -o "$key" = "-code" -o "$key" = "-accessdomain" \
            -o "$key" = "-amsdomain" -o "$key" = "-alsdomain" -o "$key" = "-clusterid" -o "$key" = "-clustername" \
            -o "$key" = "-proxy" -o "$key" = "-isapig" -o "$key" = "-aomaksk" -o "$key" = "-ltsaksk" -o "$key" = "-aomvpcepurl" -o "$key" = "-ltsvpcepurl" \
                                                                                                                 -o "$key" = "-obsvpcepurl" -o "$key" = "-agentVersion" ];
    then
        return 1
    fi
    return 0
}

function checkArgs()
{
    param_num=$#
    if [ $param_num -eq 0 ];then
        return
    fi
    
    #check options
    for i in `seq $param_num | awk 'i=!i'`
    do
        if checkOption "${!i}"
        then
            echo -e "\e[1;41mERROR\e[0m : unknown parameter \e[1;31m${!i}\e[0m"
            help
        fi
    done

    res=0;a=1;b=2;c=4;d=8;e=16;
    for i in `seq $(($param_num/2))`
    do
        [[ ${1#-} == "ak" ]] && { AK=$2;res=$[$res|$a];a=128;shift 2;continue; }
        [[ ${1#-} == "sk" ]] && { SK=$2;res=$[$res|$b];b=128;shift 2;continue; }
        [[ ${1#-} == "region" ]] && { REGION_CODE=$2;res=$[$res|$c];c=128;shift 2;continue; }
        [[ ${1#-} == "projectid" ]] && { PROJECTID=$2;res=$[$res|$d];d=128;shift 2;continue; }
        [[ ${1#-} == "obsdomain" ]] && { OBSDOMAIN=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "accessip" ]] && { ACCESSIP=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "scene" ]] && { SCENE=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "dc" ]] && { DC=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "plugoff" ]] && { PLUGOFF=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "code" ]] && { AOM_ACCESS_CODE=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "accessdomain" ]] && { ACCESSDOMAIN=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "amsdomain" ]] && { AMSDOMAIN=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "alsdomain" ]] && { ALSDOMAIN=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "aomvpcepurl" ]] && { AOM_VPCEP_URL=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "ltsvpcepurl" ]] && { LTS_VPCEP_URL=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "obsvpcepurl" ]] && { OBS_VPCEP_URL=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "clusterid" ]] && { CLUSTERID=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "clustername" ]] && { CLUSTERNAME=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "proxy" ]] && { PROXY=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "isapig" ]] && { ISAPIG=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "aomaksk" ]] && { AOM_AKSK=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "ltsaksk" ]] && { LTS_AKSK=$2;res=$[$res|$d];e=128;shift 2;continue; }
        [[ ${1#-} == "agentVersion" ]] && { AGENT_VERSION=$2;res=$[$res|$d];e=128;shift 2;continue; }
    done

}

function checkAomLtsAkSk() {
  if [ "X$AOM_AKSK" == "X" -o "X$LTS_AKSK" == "X" ];then
    echo 'param is empty '$AOM_AKSK' '$LTS_AKSK
    return
  fi

  echo $AOM_AKSK | grep -q '-'
  if [ $? -ne 0 ];then
    logError 'AOM_AKSK '$AOM_AKSK' not contains char -'
    exit
  fi

  echo $LTS_AKSK | grep -q '-'
  if [ $? -ne 0 ];then
    logError 'LTS_AKSK '$LTS_AKSK' not contains char -'
    exit
  fi
}

function downloadPackage() {
  pkgName=icagent-$AGENT_VERSION.tar.gz
  curl --progress-bar -o $PLUGIN_PATH/$pkgName -k https://${agentUrl}/ICAgent_linux/$pkgName
  if [ ! -f $PLUGIN_PATH/$pkgName ];then
    echo 'error: '$pkgName' download failed'
    exit
  fi

  tar xf $PLUGIN_PATH/$pkgName -C $PLUGIN_PATH/ > /dev/null 2>&1
  if [ $? -ne 0 ];then
    rm -rf $PLUGIN_PATH/$pkgName
    echo 'error: '$pkgName' download failed'
    exit
  fi
  chmod +x $PLUGIN_PATH/script/*
  cp $PLUGIN_PATH/package/ICProbeAgent.tar.gz $packageHome
  rm -f $PLUGIN_PATH/$pkgName

  if [ ! -f $packageHome/ICProbeAgent.tar.gz ];then
    echo 'error: '$packageHome/ICProbeAgent.tar.gz' download failed'
    exit
  fi
}

function getLatestVersion() {
  curl --progress-bar -o $packageHome/release_version.properties -k https://${agentUrl}/ICAgent_linux/release_version.properties
  if [ ! -f $packageHome/release_version.properties ];then
    echo 'error: 'release_version.properties' download failed'
    exit
  fi
  # Get version
  search_content="release_version"
  field_number=2
  latestVersion=`awk -F "=" "/$search_content/{print \$"$field_number"}" $packageHome/release_version.properties`
  rm -rf $packageHome/release_version.properties
}

function checkICAgentPath() {
    if [ -d "${PLUGIN_PATH}" ]; then
        if [ -z "$(ls -A "${PLUGIN_PATH}")" ]; then
            rmdir "${PLUGIN_PATH}"
        fi
    fi
}


#=================================main entrance=============================

CURRENT_USER="`/usr/bin/id -u -n`"
checkArgs $@

if [ "$AK" == "{input_your_ak}" -a "$SK" == "{input_your_sk}" ];then
	echo "Enter the AK:"
	read ak
	AK=$ak
	echo "Enter the SK:"
	stty -echo
	read sk
	stty echo
	SK=$sk
fi

if [ "$AOM_AKSK" == "{input_your_aomaksk}" -a "$LTS_AKSK" == "{input_your_ltsaksk}" ];then
	echo "Enter the AOM_AKSK:"
	stty -echo
	read aomaksk
	stty echo
	AOM_AKSK=$aomaksk
	echo "Enter the LTS_AKSK:"
	stty -echo
	read ltsaksk
	stty echo
	LTS_AKSK=$ltsaksk
fi

checkAomLtsAkSk

logInfo "start to install ICAgent."
packageHome=/opt/ICAgent
PLUGIN_PATH="/usr/local/uniagentd/extension/install/icagent/"
mkdir -p $packageHome;
checkICAgentPath

if [ X"$REGION" = X"" ];then
    logError "REGION lack, please refer to user installation guide"
    echo -e "Example:   "
    echo -e "    \e[1;41mREGION={region}\e[0m bash apm_agent_install.sh -ak -sk -region {region} -projectid ;";
    exit 1
fi

if [ X"${REGION_CODE}" = X"" ];then
    REGION_CODE=$REGION
fi

#default HWS
urlPostfix="obs.$REGION.myhuaweicloud.com"
if [ X"${OBSDOMAIN}" != X"" ];then
    urlPostfix=${OBSDOMAIN}
fi


agentUrl=icagent-${REGION_CODE}.${urlPostfix}
if [ X"${REPODOMAIN}" != X"" ];then
    export REPODOMAIN=$REPODOMAIN

    if [ X"${ACCESSIP}" == X"" ];then
        iparr=(${REPODOMAIN//:/ })
        ACCESSIP=${iparr[0]}
    fi

    logInfo "begin to download install package from $REPODOMAIN."
    curl --progress-bar -o $packageHome/ICProbeAgent.tar.gz -k https://${REPODOMAIN}/v1/repos/ICAgent_linux/ICProbeAgent.tar.gz;
    result=$(curl --progress-bar -o $packageHome/ICProbeAgent.tar.gz.sha256 -k -w "%{http_code}\n" https://${REPODOMAIN}/v1/repos/ICAgent_linux/ICProbeAgent.tar.gz.sha256)
    if [ "X$result" == "X200" ]; then
        sha256_refer=`sed -n 1p $packageHome/ICProbeAgent.tar.gz.sha256`
        sha256_value=`sha256sum $packageHome/ICProbeAgent.tar.gz |awk  '{print $1}'`
        if [[ "${sha256_refer}x" != "${sha256_value}x" ]]; then
           logError "check sha256 failed,exit"
           exit 1
        fi
    else
        echo 'download 'ICProbeAgent.tar.gz.sha256' failed, result:'$result
    fi
else
    mkdir -p $PLUGIN_PATH
    getLatestVersion

    if [ X"" != X"$AGENT_VERSION" ];then
      downloadPackage
    else
      logInfo "begin to download install package from $agentUrl."
      curl --progress-bar -o $PLUGIN_PATH/icagent-$latestVersion.tar.gz -k https://${agentUrl}/ICAgent_linux/icagent-$latestVersion.tar.gz;
      curl --progress-bar -o $PLUGIN_PATH/icagent-$latestVersion.tar.gz.sha256 -k https://${agentUrl}/ICAgent_linux/icagent-$latestVersion.tar.gz.sha256;
      sha256_refer=`sed -n 1p $PLUGIN_PATH/icagent-$latestVersion.tar.gz.sha256`
      sha256_value=`sha256sum $PLUGIN_PATH/icagent-$latestVersion.tar.gz |awk  '{print $1}'`
      if [[ "${sha256_refer}x" != "${sha256_value}x" ]]; then
         logError "check sha256 failed,exit"
         exit 1
      fi
      logInfo "check sha256 success,start"
      tar xf $PLUGIN_PATH/icagent-$latestVersion.tar.gz -C $PLUGIN_PATH/ > /dev/null 2>&1
        if [ $? -ne 0 ];then
          rm -rf $PLUGIN_PATH/icagent-$latestVersion.tar.gz
          rm -rf $PLUGIN_PATH/icagent-$latestVersion.tar.gz.sha256
          echo 'error: 'icagent-$latestVersion.tar.gz' download failed'
          exit
        fi
        chmod +x $PLUGIN_PATH/script/*
        cp $PLUGIN_PATH/package/ICProbeAgent.tar.gz $packageHome
        rm -rf $PLUGIN_PATH/icagent-$latestVersion.tar.gz
        rm -rf $PLUGIN_PATH/icagent-$latestVersion.tar.gz.sha256
    fi
fi

if [ $? != 0 ]
then
    logError "download install package failed, please retry"
    exit 1;
fi
logInfo "download success."
logInfo "start install package."
tar -zxvf $packageHome/ICProbeAgent.tar.gz -C $packageHome >/dev/null 2>&1
chmod -R 750 $packageHome >/dev/null 2>&1

if [ X"${SCENE}" = X"internet" -a X"$ACCESSIP" = X"" ];then
    logError  "accessip is essential args, please input."
    help
    exit 1
fi


#special process
if [ X"${REGION_CODE}" = X"" ];then
    REGION_CODE="reserved_region"
fi
if [ X"${OBSDOMAIN}" = X"" ];then
    OBSDOMAIN="obs.$REGION_CODE.myhuaweicloud.com"
fi
if [ X"${SCENE}" = X"" ];then
    SCENE="hws"
fi
if [ X"${PLUGOFF}" = X"" ];then
    PLUGOFF="reserved"
fi
if [ X"${ISAPIG}" = X"" ];then
    ISAPIG="false"
fi

aomVpcepUrlArgs=
if [ X"${AOM_VPCEP_URL}" != X"" ]; then
    aomVpcepUrlArgs='-aomvpcepurl '${AOM_VPCEP_URL}
fi

ltsVpcepUrlArgs=
if [ X"${LTS_VPCEP_URL}" != X"" ]; then
    ltsVpcepUrlArgs='-ltsvpcepurl '${LTS_VPCEP_URL}
fi

obsVpcepUrlArgs=
if [ X"${OBS_VPCEP_URL}" != X"" ]; then
    obsVpcepUrlArgs='-obsvpcepurl '${OBS_VPCEP_URL}
fi

mgrArg=
if [ X"${ACCESSDOMAIN}" != X"" ];then
    mgrArg='-accessdomain '$ACCESSDOMAIN
fi

AmsArg=
if [ X"${AMSDOMAIN}" != X"" ];then
  AmsArg='-amsdomain '$AMSDOMAIN
fi

AlsArg=
if [ X"${ALSDOMAIN}" != X"" ];then
  AlsArg='-alsdomain '$ALSDOMAIN
fi

clusterArg=
if [ X"$CLUSTERID" != X"" -a X"$CLUSTERNAME" != X"" ];then
  clusterArg=" -clusterid $CLUSTERID -clustername $CLUSTERNAME"
fi

proxyArg=
if [ X"${PROXY}" != X"" ];then
    proxyArg="-proxy "$PROXY
fi

dcArgs=
if [ X"${DC}" != X"" ];then
  dcArgs="-dc "$${DC}
fi

userArgs=
if [ X"${CURRENT_USER}" != X"" ];then
  userArgs="-user "${CURRENT_USER}
fi


#old args format
if [ X"${AK}" != X"" ];then
    if [ X"${ACCESSIP}" == X"" ];then
        bash $packageHome/bin/manual/setup.sh -ak $AK -sk $SK -projectid $PROJECTID -region $REGION_CODE -plugoff $PLUGOFF -isapig $ISAPIG -obsdomain $OBSDOMAIN $proxyArg $AmsArg $AlsArg $clusterArg $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArgs $userArgs;
    else
        bash $packageHome/bin/manual/setup.sh -ak $AK -sk $SK -projectid $PROJECTID -region $REGION_CODE -ip $ACCESSIP:9999 $mgrArg -plugoff $PLUGOFF -isapig $ISAPIG -obsdomain $OBSDOMAIN $proxyArg -scene $SCENE $AmsArg $AlsArg $clusterArg $dcArgs $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArgs $userArgs;
    fi
# The new installation method uses the icmgr self-issued AK\SK authentication mechanism.
elif [ X"${AOM_AKSK}" != X"" -a X"${LTS_AKSK}" != X"" ];then
    if [ X"${ACCESSIP}" == X"" ];then
            bash $packageHome/bin/manual/setup.sh -aomaksk $AOM_AKSK -ltsaksk $LTS_AKSK -projectid $PROJECTID -region $REGION_CODE -plugoff $PLUGOFF -isapig $ISAPIG -obsdomain $OBSDOMAIN $proxyArg $AmsArg $AlsArg $clusterArg $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArgs $userArgs;
        else
            bash $packageHome/bin/manual/setup.sh -aomaksk $AOM_AKSK -ltsaksk $LTS_AKSK -projectid $PROJECTID -region $REGION_CODE -ip $ACCESSIP:9999 $mgrArg -plugoff $PLUGOFF -isapig $ISAPIG -obsdomain $OBSDOMAIN $proxyArg -scene $SCENE $AmsArg $AlsArg $clusterArg $dcArgs $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArg $userArgs;
    fi
else
    #new args format, just support two format bellows
    #bash apm_agent_install.sh -accessip 1.2.3.4
    #bash apm_agent_install.sh -accessip 1.2.3.4 -obsdomain obs.xxxx.xxx

    #accessip is essential args
    if [ X"${ACCESSIP}" == X"" ];then
        logError  "accessip is essential args, please input."
        help
        exit 1
    fi
    if [ X"${AOM_ACCESS_CODE}" == X"" ];then
        response=$(curl -w "%{http_code}" -s -o /dev/null  -X PUT "http://169.254.169.254/meta-data/latest/api/token" -H "X-Metadata-Token-Ttl-Seconds: 21600")
        if [ "${response}x" == "200x" ]; then
            metaVersion="v2"
            token=`curl -s  -X PUT "http://169.254.169.254/meta-data/latest/api/token" -H "X-Metadata-Token-Ttl-Seconds: 21600"`
        fi

        if [ "${metaVersion}x" == "v2x" ]; then
          retcode=`curl --connect-timeout 5 -m 5 -o /dev/null -s -w %{http_code}  http://169.254.169.254/openstack/latest/securitykey -H "X-Metadata-Token:$token"`
        else
          retcode=`curl --connect-timeout 5 -m 5 -o /dev/null -s -w %{http_code}  http://169.254.169.254/openstack/latest/securitykey`
        fi
        if [ X"$retcode" != X"200" ];then
            logError "can't get securitykey info from openstack, please check ecs agency."
            exit 1
        fi
        bash $packageHome/bin/manual/setup.sh -ip $ACCESSIP:9999 $mgrArg -plugoff $PLUGOFF -isapig $ISAPIG -region $REGION_CODE -obsdomain $OBSDOMAIN $proxyArg $AmsArg $AlsArg $clusterArg $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArgs;
    else
        bash $packageHome/bin/manual/setup.sh -ip $ACCESSIP:9999 $mgrArg -plugoff $PLUGOFF -isapig $ISAPIG -projectid $PROJECTID -region $REGION_CODE -obsdomain $OBSDOMAIN $proxyArg -code $AOM_ACCESS_CODE $AmsArg $AlsArg $clusterArg $aomVpcepUrlArgs $ltsVpcepUrlArgs $obsVpcepUrlArgs;
    fi
fi

if [ -d $packageHome ];then
        chmod 600 $packageHome/release_version.properties
        chmod 600 $packageHome/envs/*
        chmod 600 $packageHome/config/*
        rm -f $packageHome/bin/arch/aarch64/.gitkeep >/dev/null 2>&1
        rm -f $packageHome/bin/arch/x86_64/.gitkeep >/dev/null 2>&1
        if [ "root" == "${CURRENT_USER}" ];then
            chmod -R 550 $packageHome/bin >/dev/null 2>&1
        fi
fi
