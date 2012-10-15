#+
# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.utils.translation import ugettext as _

from freenasUI import choices
from freenasUI.freeadmin.api.utils import (DojoModelResource,
    DjangoAuthentication)
from freenasUI.network.models import (Interfaces, LAGGInterface,
    LAGGInterfaceMembers)
from freenasUI.sharing.models import NFS_Share
from freenasUI.system.models import CronJob, Rsync, SMARTTest
from freenasUI.storage.models import Disk, Volume, Scrub, Task


def _common_human_fields(bundle):
    for human in ('human_minute', 'human_hour', 'human_daymonth',
            'human_month', 'human_dayweek'):
        method = getattr(bundle.obj, "get_%s" % human, None)
        if not method:
            continue
        bundle.data[human] = getattr(bundle.obj, "get_%s" % human)()


class DiskResource(DojoModelResource):

    class Meta:
        queryset = Disk.objects.filter(
            disk_enabled=True,
            disk_multipath_name=''
            ).exclude(
                Q(disk_name__startswith='multipath') | Q(disk_name='')
            )
        resource_name = 'disk'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(DiskResource, self).dehydrate(bundle)
        bundle.data['_edit_url'] += '?deletable=false'
        bundle.data['_wipe_url'] = reverse('storage_disk_wipe', kwargs={
            'devname': bundle.obj.disk_name,
            })
        return bundle


class Uid(object):
    def __init__(self, start):
        self._start = start
        self._counter = start

    def next(self):
        number = self._counter
        self._counter += 1
        return number


class VolumeResource(DojoModelResource):

    class Meta:
        queryset = Volume.objects.all()
        resource_name = 'volume'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def _get_datasets(self, vol, datasets, uid):
        children = []
        attr_fields = ('total_si', 'avail_si', 'used_si', 'used_pct')
        for name, dataset in datasets.items():
            data = {
                'id': uid.next(),
                'name': name,
                'type': 'dataset',
                'status': vol.status,
                'mountpoint': dataset.mountpoint,
                'path': dataset.path,
            }
            for attr in attr_fields:
                data[attr] = getattr(dataset, attr)

            data['used'] = "%s (%s)" % (
                data['used_si'],
                data['used_pct'],
                )

            data['_dataset_delete_url'] = reverse('storage_dataset_delete',
                kwargs={
                'name': dataset.path,
                })
            data['_dataset_edit_url'] = reverse('storage_dataset_edit',
                kwargs={
                'dataset_name': dataset.path,
                })
            data['_dataset_create_url'] = reverse('storage_dataset', kwargs={
                'fs': dataset.path,
                })
            data['_permissions_url'] = reverse('storage_mp_permission',
                kwargs={
                'path': dataset.mountpoint,
                })
            data['_manual_snapshot_url'] = reverse('storage_manualsnap',
                kwargs={
                'fs': dataset.path,
                })

            if dataset.children:
                _datasets = {}
                for child in dataset.children:
                    _datasets[child.name] = child
                data['children'] = self._get_datasets(vol, _datasets, uid)

            children.append(data)
        return children

    def dehydrate(self, bundle):
        bundle = super(VolumeResource, self).dehydrate(bundle)
        mp = bundle.obj.mountpoint_set.all()[0]

        bundle.data['name'] = bundle.obj.vol_name
        bundle.data['_detach_url'] = reverse('storage_detach', kwargs={
            'vid': bundle.obj.id,
            })
        bundle.data['_scrub_url'] = reverse('storage_scrub', kwargs={
            'vid': bundle.obj.id,
            })
        bundle.data['_options_url'] = reverse('storage_volume_edit', kwargs={
            'object_id': mp.id,
            })
        bundle.data['_add_dataset_url'] = reverse('storage_dataset', kwargs={
            'fs': bundle.obj.vol_name,
            })
        bundle.data['_add_zfs_volume_url'] = reverse('storage_zvol', kwargs={
            'volume_name': bundle.obj.vol_name,
            })
        bundle.data['_permissions_url'] = reverse('storage_mp_permission',
            kwargs={
            'path': mp.mp_path,
            })
        bundle.data['_status_url'] = reverse('storage_volume_status', kwargs={
            'vid': bundle.obj.id,
            })
        bundle.data['_manual_snapshot_url'] = reverse('storage_manualsnap',
            kwargs={
            'fs': bundle.obj.vol_name,
            })
        bundle.data['_unlock_url'] = reverse('storage_volume_unlock',
            kwargs={
            'object_id': bundle.obj.id,
            })
        bundle.data['_download_key_url'] = reverse('storage_volume_key',
            kwargs={
            'object_id': bundle.obj.id,
            })
        bundle.data['_rekey_url'] = reverse('storage_volume_rekey',
            kwargs={
            'object_id': bundle.obj.id,
            })
        bundle.data['_add_reckey_url'] = reverse(
            'storage_volume_recoverykey_add',
            kwargs={'object_id': bundle.obj.id})
        bundle.data['_rem_reckey_url'] = reverse(
            'storage_volume_recoverykey_remove',
            kwargs={'object_id': bundle.obj.id})
        bundle.data['_create_passphrase_url'] = reverse(
            'storage_volume_create_passphrase',
            kwargs={'object_id': bundle.obj.id})
        bundle.data['_change_passphrase_url'] = reverse(
            'storage_volume_change_passphrase',
            kwargs={'object_id': bundle.obj.id})
        bundle.data['is_decrypted'] = bundle.obj.is_decrypted()

        attr_fields = ('total_si', 'avail_si', 'used_si', 'used_pct')
        for attr in attr_fields + ('status', ):
            bundle.data[attr] = getattr(mp, attr)

        if bundle.obj.is_decrypted():
            bundle.data['used'] = "%s (%s)" % (
                bundle.data['used_si'],
                bundle.data['used_pct'],
                )
        else:
            bundle.data['used'] = _("Locked")

        bundle.data['mountpoint'] = mp.mp_path

        uid = Uid(bundle.obj.id * 100)

        children = self._get_datasets(
            bundle.obj,
            bundle.obj.get_datasets(hierarchical=True),
            uid=uid,
            )

        zvols = bundle.obj.get_zvols() or {}
        for name, zvol in zvols.items():
            data = {
                'id': uid.next(),
                'name': name,
                'status': mp.status,
                'type': 'zvol',
                'total_si': zvol['volsize'],
            }

            data['_zvol_delete_url'] = reverse('storage_zvol_delete', kwargs={
                'name': name,
                })
            data['_manual_snapshot_url'] = reverse('storage_manualsnap',
                kwargs={
                'fs': name,
                })

            children.append(data)

        bundle.data['children'] = children
        return bundle


class ScrubResource(DojoModelResource):

    class Meta:
        queryset = Scrub.objects.all()
        resource_name = 'scrub'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ScrubResource, self).dehydrate(bundle)
        bundle.data['scrub_volume'] = bundle.obj.scrub_volume.vol_name

        for human in ('human_minute', 'human_hour', 'human_daymonth',
                'human_month', 'human_dayweek'):
            bundle.data[human] = getattr(bundle.obj, "get_%s" % human)()
        return bundle


class TaskResource(DojoModelResource):

    class Meta:
        queryset = Task.objects.all()
        resource_name = 'task'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(TaskResource, self).dehydrate(bundle)
        if bundle.obj.task_repeat_unit == "daily":
            repeat = _('everyday')
        elif bundle.obj.task_repeat_unit == "weekly":
            wchoices = dict(choices.WEEKDAYS_CHOICES)
            labels = []
            for w in eval(bundle.obj.task_byweekday):
                labels.append(unicode(wchoices[str(w)]))
            days = ', '.join(labels)
            repeat = _('on every %(days)s') % {
                'days': days,
                }
        else:
            repeat = ''
        bundle.data['how'] = _("From %(begin)s through %(end)s, every "
            "%(interval)s %(repeat)s") % {
                'begin': bundle.obj.task_begin,
                'end': bundle.obj.task_end,
                'interval': bundle.obj.get_task_interval_display(),
                'repeat': repeat,
            }
        bundle.data['keepfor'] = "%s %s" % (
            bundle.obj.task_ret_count,
            bundle.obj.task_ret_unit,
            )
        return bundle


class NFSShareResource(DojoModelResource):

    class Meta:
        queryset = NFS_Share.objects.all()
        resource_name = 'nfs_share'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(NFSShareResource, self).dehydrate(bundle)
        bundle.data['nfs_paths'] = bundle.obj.nfs_paths
        return bundle


class InterfacesResource(DojoModelResource):

    class Meta:
        queryset = Interfaces.objects.all()
        resource_name = 'interfaces'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(InterfacesResource, self).dehydrate(bundle)
        bundle.data['ipv4_addresses'] = bundle.obj.get_ipv4_addresses()
        bundle.data['ipv6_addresses'] = bundle.obj.get_ipv6_addresses()
        return bundle


class LAGGInterfaceResource(DojoModelResource):

    class Meta:
        queryset = LAGGInterface.objects.all()
        resource_name = 'lagginterface'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceResource, self).dehydrate(bundle)
        bundle.data['lagg_interface'] = unicode(bundle.obj)
        bundle.data['int_interface'] = bundle.obj.lagg_interface.int_interface
        bundle.data['int_name'] = bundle.obj.lagg_interface.int_name
        bundle.data['_edit_url'] = reverse(
            'freeadmin_network_interfaces_edit', kwargs={
                'oid': bundle.obj.lagg_interface.id,
                }) + '?deletable=false'
        bundle.data['_delete_url'] = reverse(
            'freeadmin_network_interfaces_delete', kwargs={
                'oid': bundle.obj.lagg_interface.id,
                })
        bundle.data['_members_url'] = reverse(
            'freeadmin_network_lagginterfacemembers_datagrid'
            ) + '?id=%d' % bundle.obj.id
        return bundle


class LAGGInterfaceMembersResource(DojoModelResource):

    class Meta:
        queryset = LAGGInterfaceMembers.objects.all()
        resource_name = 'lagginterfacemembers'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def build_filters(self, filters=None):
        if filters is None:
            filters = {}
        orm_filters = super(LAGGInterfaceMembersResource,
            self).build_filters(filters)
        lagggrp = filters.get("lagg_interfacegroup__id")
        if lagggrp:
            orm_filters["lagg_interfacegroup__id"] = lagggrp
        return orm_filters

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceMembersResource, self).dehydrate(bundle)
        bundle.data['lagg_interfacegroup'] = unicode(
            bundle.obj.lagg_interfacegroup
            )
        return bundle


class CronJobResource(DojoModelResource):

    class Meta:
        queryset = CronJob.objects.all()
        resource_name = 'cronjob'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(CronJobResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        return bundle


class RsyncResource(DojoModelResource):

    class Meta:
        queryset = Rsync.objects.all()
        resource_name = 'rsync'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(RsyncResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        return bundle


class SMARTTestResource(DojoModelResource):

    class Meta:
        queryset = SMARTTest.objects.all()
        resource_name = 'smarttest'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(SMARTTestResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        bundle.data['smarttest_type'] = bundle.obj.get_smarttest_type_display()
        return bundle