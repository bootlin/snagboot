# Troubleshooting

## AttributeError: /usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so: undefined symbol: hid_get_input_report 
This is related to hid 1.0.5 using a symbol which isn't supported in your
version of libhidapi-hidraw0. Downgrading to hid==1.0.4 should fix the issue: 

```bash
python3 -m pip uninstall hid
python3 -m pip install hid==1.0.4
```

