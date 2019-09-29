# coding: utf-8

import os
import shutil
import click
import massedit
from tabulate import tabulate
from compose.cli.main import project_from_options
from template import Jinja2


@click.group()
@click.option('--etc-dir', default='./etc')
@click.pass_context
def cli(ctx, etc_dir):
    ctx.obj['etc'] = etc_dir


@cli.command('ps')
@click.option('--all', 'show_all', is_flag=True)
@click.option('--cluster-name', default=None)
@click.pass_context
def ps(ctx, show_all, cluster_name):
    if show_all:
        ps_all_project(ctx)
    elif cluster_name:
        ps_one_project(ctx, cluster_name)


def ps_all_project(ctx):
    cluster_names = os.listdir(ctx.obj['etc'])
    for cluster_name in cluster_names:
        # ... 
        if cluster_name == '.gitkeep':
            continue
        ps_one_project(ctx, cluster_name)


def ps_one_project(ctx, cluster_name):
    cluster_dir = os.path.join(ctx.obj['etc'], cluster_name)
    if not os.path.exists(cluster_dir):
        click.echo(click.style('wrong cluster name', fg='red', bold=True))
        ctx.exit(-1)

    project = project_from_options(cluster_dir, {})
    header, body = ['service type', 'service address'], []
    # 其实都只有一个
    tidb_container = [c for s in project.services if 'tidb' in s.name for c in s.containers()][0]
    tidb_port = tidb_container.inspect()['NetworkSettings']['Ports']
    tidb_address = 'localhost:{}'.format(tidb_port['4000/tcp'][0].get('HostPort', 'unknown'))

    grafana_container = [c for s in project.services if 'grafana' in s.name for c in s.containers()][0]
    grafana_port = grafana_container.inspect()['NetworkSettings']['Ports']
    grafana_address = 'localhost:{}'.format(grafana_port['3000/tcp'][0].get('HostPort', 'unknown'))
    service_info = tabulate([
        ('tidb', tidb_address),
        ('grafana', grafana_address),
        ], headers=['service type', 'service address'])

    body = []
    for service in project.services:
        containers = service.containers()
        containers_status = [c.inspect() for c in containers]
        running = len([c for c in containers_status if c['State']['Status'] == 'running'])
        body.append((service.name, '{}/{} running/total containers'.format(running, len(containers_status))))
    service_status = tabulate(body, headers=['service name', 'container status'])

    click.echo(tabulate(
        [(cluster_name, service_info, service_status)],
        ['cluster name', 'service info', 'service status'],
        tablefmt='fancy_grid',
        ))


@cli.command('create')
@click.argument('base', default=None)
@click.argument('network', default=None)
@click.argument('clustername', default=None)
@click.option('--pd-count', default=3, type=int)
@click.option('--tikv-count', default=3, type=int)
@click.option('--tidb-version', default='latest')
@click.pass_context
def create(ctx, base, network, clustername, pd_count, tikv_count, tidb_version):
    if not base:
        click.echo(click.style('base dir must be given', fg='red', bold=True))
        ctx.exit(-1)
    if os.path.exists(base) and os.path.isdir(base):
        click.echo(click.style('base already exists, plz clean it or choose an other base', fg='red', bold=True))
        ctx.exit(-1)
    if not network:
        click.echo(click.style('network must be given', fg='red', bold=True))
        ctx.exit(-1)
    create_cluster(ctx, base, network, clustername, pd_count, tikv_count, tidb_version)


def create_cluster(ctx, base, network, cluster_name, pd_count, tikv_count, tidb_version):
    cluster_dir = os.path.join(ctx.obj['etc'], cluster_name)
    # config
    pdservices = [{
            'name': 'pd_{}_{}'.format(cluster_name, index),
            'base': os.path.abspath(base),
            'image': 'pingcap/pd:latest',
        } for index in range(pd_count)]
    tikvservices = [{
            'name': 'tikv_{}_{}'.format(cluster_name, index),
            'base': os.path.abspath(base),
            'image': 'pingcap/tikv:latest',
        } for index in range(tikv_count)]
    tidb = {
        'base': os.path.abspath(base),
        'image': 'pingcap/tidb:{}'.format(tidb_version),
    }
    monitor = {'base': os.path.abspath(base)}

    # ensure dir exists
    ensure_dir(base)
    ensure_dir(os.path.join(base, 'data'))
    ensure_dir(os.path.join(base, 'logs'))
    ensure_dir(cluster_dir)

    # create config
    shutil.copytree('./config', os.path.join(base, 'config'))

    # edit some configs
    filenames = [os.path.join(base, 'config/grafana/provisioning/datasources/datasources.yaml')]
    massedit.edit_files(filenames, ["re.sub(r'prometheus:9090', 'prometheus_{}:9090', line)".format(cluster_name)], dry_run=False)

    filenames = [os.path.join(base, 'prometheus.yml')]
    massedit.edit_files(filenames, ["re.sub(r'pushgateway:9091', 'pushgateway_{}:9091', line)".format(cluster_name)], dry_run=False)

    # keep docker-compose.yml
    tp = Jinja2(__name__)
    content = tp.render_template('/docker_compose.jinja', network=network, pdservices=pdservices,
            tikvservices=tikvservices, tidb=tidb, monitor=monitor, cluster_name=cluster_name)
    filename = os.path.join(cluster_dir, 'docker-compose.yml')
    with open(filename, 'w') as f:
        f.write(content)

    project = project_from_options(cluster_dir, {})
    project.up(detached=True)
    click.echo(click.style('cluster {} created'.format(cluster_name), fg='green'))


def ensure_dir(path):
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def ensure_dir_absent(path):
    if os.path.lexists(path):
        if os.path.islink(path):
            os.unlink(path)
        else:
            shutil.rmtree(path, ignore_errors=True)


@cli.command('rm')
@click.argument('clustername')
@click.option('--volumes', is_flag=True)
@click.pass_context
def rm(ctx, clustername, volumes):
    cluster_dir = os.path.join(ctx.obj['etc'], clustername)
    if not os.path.exists(cluster_dir):
        click.echo(click.style('wrong cluster name', fg='red', bold=True))
        ctx.exit(-1)
    project = project_from_options(cluster_dir, {})
    project.down(remove_image_type=0, include_volumes=volumes)
    ensure_dir_absent(cluster_dir)

    click.echo(click.style('cluster {} removed'.format(clustername), fg='green'))


if __name__ == '__main__':
    cli(obj={})
