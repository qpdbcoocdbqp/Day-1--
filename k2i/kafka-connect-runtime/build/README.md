# Build kafka-connect-runtime required JAR files

### Clone apache/iceberg and build kafka-connect-runtime

* **IMPORTANT**: Here `assemble` instead of `build`. To skip `check` section.

```sh
cd k2i
git clone https://github.com/apache/iceberg.git
cd iceberg
docker build -f ../kafka-connect-runtime/docker/dockerfile --output ./build-output .

# check `iceberg-kafka-connect-runtime.zip` `iceberg-kafka-connect-runtime-hive.zip`
ls ./build-output/distributions
```

### Move JAR files to build/install

```sh
mkdir -p k2i/kafka-connect-runtime/build/install
cd k2i/kafka-connect-runtime/build/install
unzip ../../../iceberg/build-output/distributions/iceberg-kafka-connect-runtime.zip
```
