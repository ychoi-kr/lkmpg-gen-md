20. Common Pitfalls

<a name="sec:using_stdlib"></a>
## 20.1. Using standard libraries

You can not do that. In a kernel module, you can only use kernel functions which are the functions you can see in `/proc/kallsyms`.

<a name="sec:disabling_interrupts"></a>
## 20.2. Disabling interrupts

You might need to do this for a short time and that is OK, but if you do not enable them afterwards, your system will be stuck and you will have to power it off.
