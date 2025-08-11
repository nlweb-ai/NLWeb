# Check connectivity script
This is a simple tool to ensure that your NLWeb environment is configured properly.  

## How to run
By default, this tool checks that only the configured options (set in your config yaml files in the [config directory](../code/config/)) are set with valid endpoints.  This will ensure that your instance of NLWeb is configured properly.  

```bash
# Run from the code directory
> python code/python/testing/check_connectivity.py
```

In addition, you can leverage the `--all` parameter option to test connectivity for every known configuration from all config files.  This can be useful for automated testing suites.  

```bash
# Run from the code directory
> python code/python/testing/check_connectivity.py --all
```


