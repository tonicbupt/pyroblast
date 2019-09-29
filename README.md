# Pyroblast

## 思路

* 先快速搞吧, 所以直接用了 `docker-compose` 的库
* `project` 的 `up` / `down` / `ps` 这些都直接用了 `compose` 或者是 `docker` 提供的 API
* 最简单的方法就是用基于 docker-compose.yml 的配置管理, 做好配置文件之后, 一个配置文件就是一个 compose 的集群
* 网络用 `docker network` 来隔离就可以了, 注意需要 expose 的端口, 以及需要 publish 的端口
* volume 可以直接用本地的不同目录来隔离, 毕竟只是一个测试...
* 接下来的工作就基本是一些监控的配置文件替换了

## 缺点

* 一些监控配置不是那么好替换, 比如 grafana 需要在容器启动之后才知道自己的 port, 然而配置需要在容器启动之前就确定. 一个 walkaround 是 stop 一次 container 修改配置重新启动...
* 自己的小 MacBook 开两个集群直接跑满... `down` 掉其中一个才能能继续响应另外一个, 所以没有做太多多集群的测试了, 单个集群看起来是可以的
* `base` 其实是可以指定不同目录来替换的, 不过好像也没有要求这一点所以都用了同一个, 也不影响测试

## 服用方法

* Install

```
$ virtualenv venv
$ source venv/bin/active
$ pip install -r requirements.txt
```
然后就可以

```
$ ./pyroblast --help
Usage: pyroblast.py [OPTIONS] COMMAND [ARGS]...

Options:
  --etc-dir TEXT
  --help          Show this message and exit.

Commands:
  create
  ps
  rm
```

* 创建一个集群

```
$ ./pyroblast create /Users/tonic/tidbyyy tidb1 dalaran --tikv-count 1 --pd-count 1
```

要注意这个 `tidb1` 的 network 需要先 `docker network create tidb1` 一下, 并且 `/Users/tonic/tidbyyy` 这个 base dir 需要不存在, 存在会有错误提示. 在销毁集群的时候不会删除这个目录, 还是留一下数据吧万一有用呢...

* 列出集群

```
$ ./pyroblast ps --all
╒════════════════╤═══════════════════════════════════╤═══════════════════════════════════════════════════╕
│ cluster name   │ service info                      │ service status                                    │
╞════════════════╪═══════════════════════════════════╪═══════════════════════════════════════════════════╡
│ dalaran        │ service type    service address   │ service name         container status             │
│                │ --------------  ----------------- │ -------------------  ---------------------------- │
│                │ tidb            localhost:32868   │ pd_dalaran_0         1/1 running/total containers │
│                │ grafana         localhost:32866   │ tikv_dalaran_0       1/1 running/total containers │
│                │                                   │ tidb_dalaran         1/1 running/total containers │
│                │                                   │ pushgateway_dalaran  1/1 running/total containers │
│                │                                   │ prometheus_dalaran   1/1 running/total containers │
│                │                                   │ grafana_dalaran      1/1 running/total containers │
╘════════════════╧═══════════════════════════════════╧═══════════════════════════════════════════════════╛
╒════════════════╤═══════════════════════════════════╤════════════════════════════════════════════════════╕
│ cluster name   │ service info                      │ service status                                     │
╞════════════════╪═══════════════════════════════════╪════════════════════════════════════════════════════╡
│ zandalar       │ service type    service address   │ service name          container status             │
│                │ --------------  ----------------- │ --------------------  ---------------------------- │
│                │ tidb            localhost:32873   │ pd_zandalar_0         1/1 running/total containers │
│                │ grafana         localhost:32871   │ tikv_zandalar_0       1/1 running/total containers │
│                │                                   │ tidb_zandalar         1/1 running/total containers │
│                │                                   │ pushgateway_zandalar  1/1 running/total containers │
│                │                                   │ prometheus_zandalar   1/1 running/total containers │
│                │                                   │ grafana_zandalar      1/1 running/total containers │
╘════════════════╧═══════════════════════════════════╧════════════════════════════════════════════════════╛
```

因为用了网络做隔离所以单机上也没办法把服务都 publish 到指定端口, 所以需要从 container 的 inspect 里面来看, 就让 docker 自己去分配吧

* 销毁一个集群

```
$ ./pyroblast rm zandalar
```