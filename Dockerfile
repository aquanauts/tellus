FROM ubuntu:bionic-20200311

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
  acl \
  apt-transport-https \
  ca-certificates \
  curl \
  git \
  gawk \
  gnupg-agent \
  jq \
  lsof \
  make \
  net-tools \
  rsync \
  software-properties-common \
  sshfs \
  tzdata \
  unzip \
  wget \
  xz-utils \
  zstd \
 && rm -rf /var/lib/apt/lists/*

# Install miniconda directly into /opt/miniconda3.
RUN curl -sL "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" -o /tmp/miniconda.sh &&\
    chmod +x /tmp/miniconda.sh &&\
    /tmp/miniconda.sh -b -p /opt/miniconda3 &&\
    rm /tmp/miniconda.sh &&\
    chmod -R 777 /opt/miniconda3/ &&\
    setfacl -d -m u::rwx /opt/miniconda3/ &&\
    setfacl -d -m g::rwx /opt/miniconda3/ &&\
    setfacl -d -m o::rwx /opt/miniconda3/

ENV PATH="/opt/miniconda3/bin:/root/.ozy/bin:${PATH}"

ADD environment.yml .
RUN conda env update --name base --file environment.yml

COPY . /opt/tellus
WORKDIR /opt/tellus
ENV PYTHONPATH /opt/tellus

CMD ["/opt/miniconda3/bin/python3", "tellus"]
