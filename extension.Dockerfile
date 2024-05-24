RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    luarocks install lua-resty-openssl && \
    luarocks install lua-resty-http
