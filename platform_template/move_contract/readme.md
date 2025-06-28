请将move合约部署文件直接放置在该文件夹下。

为了优化链上部署速度，请按照下面方式在 Move.toml 使用本地依赖:
```toml
[dependencies]
Sui = { local = "/app/sui/crates/sui-framework/packages/sui-framework" }
```
