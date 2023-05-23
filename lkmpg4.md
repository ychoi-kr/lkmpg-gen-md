4. Hello World

<a name="sec:org2d3e245"></a>

## 4.1. The Simplest Module

Most people learning programming start out with some sort of "*hello world*" example. I don't know what happens to people who break with this tradition, but I think it is safer not to find out. We will start with a series of hello world programs that demonstrate the different aspects of the basics of writing a kernel module.

Here is the simplest module possible.

Make a test directory:

    mkdir -p ~/develop/kernel/hello-1
    cd ~/develop/kernel/hello-1

Paste this into your favorite editor and save it as `hello-1.c`:

    /*
     * hello-1.c - The simplest kernel module.
     */
    #include <linux/module.h> /* Needed by all modules */
    #include <linux/printk.h> /* Needed for pr_info() */

    int init_module(void)
    {
        pr_info("Hello world 1.\n");

        /* A non 0 return means init_module failed; module can't be loaded. */
        return 0;
    }

    void cleanup_module(void)
    {
        pr_info("Goodbye world 1.\n");
    }

    MODULE_LICENSE("GPL");

Now you will need a `Makefile`. If you copy and paste this, change the indentation to use *tabs*, not spaces.

    obj-m += hello-1.o

    PWD := $(CURDIR)

    all:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

    clean:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean

In `Makefile`, `$(CURDIR)` can set to the absolute pathname of the current working directory(after all `-C` options are processed, if any). See more about `CURDIR` in [GNU make manual](https://www.gnu.org/software/make/manual/make.html).

And finally, just run `make` directly.

    make

If there is no `PWD := $(CURDIR)` statement in Makefile, then it may not compile correctly with `sudo make`. Because some environment variables are specified by the security policy, they can't be inherited. The default security policy is `sudoers`. In the `sudoers` security policy, `env_reset` is enabled by default, which restricts environment variables. Specifically, path variables are not retained from the user environment, they are set to default values (For more information see: [sudoers manual](https://www.sudo.ws/docs/man/sudoers.man/)). You can see the environment variable settings by:

    $ sudo -s
    # sudo -V

Here is a simple Makefile as an example to demonstrate the problem mentioned above.

    all:
        echo $(PWD)

Then, we can use `-p` flag to print out the environment variable values from the Makefile.

    $ make -p | grep PWD
    PWD = /home/ubuntu/temp
    OLDPWD = /home/ubuntu
        echo $(PWD)

The `PWD` variable won't be inherited with `sudo`.

    $ sudo make -p | grep PWD
        echo $(PWD)

However, there are three ways to solve this problem.

1.  You can use the `-E` flag to temporarily preserve them.

            $ sudo -E make -p | grep PWD
            PWD = /home/ubuntu/temp
            OLDPWD = /home/ubuntu
            echo $(PWD)

2.  You can set the `env_reset` disabled by editing the `/etc/sudoers` with root and `visudo`.

          ## sudoers file.
          ## 
          ...
          Defaults env_reset
          ## Change env_reset to !env_reset in previous line to keep all environment variables

    Then execute `env` and `sudo env` individually.

            # disable the env_reset
            echo "user:" > non-env_reset.log; env >> non-env_reset.log
            echo "root:" >> non-env_reset.log; sudo env >> non-env_reset.log
            # enable the env_reset
            echo "user:" > env_reset.log; env >> env_reset.log
            echo "root:" >> env_reset.log; sudo env >> env_reset.log

    You can view and compare these logs to find differences between `env_reset` and `!env_reset`.

3.  You can preserve environment variables by appending them to `env_keep` in `/etc/sudoers`.

          Defaults env_keep += "PWD"

    After applying the above change, you can check the environment variable settings by:

            $ sudo -s
            # sudo -V

If all goes smoothly you should then find that you have a compiled `hello-1.ko` module. You can find info on it with the command:

    modinfo hello-1.ko

At this point the command:

    sudo lsmod | grep hello

should return nothing. You can try loading your shiny new module with:

    sudo insmod hello-1.ko

The dash character will get converted to an underscore, so when you again try:

    sudo lsmod | grep hello

you should now see your loaded module. It can be removed again with:

    sudo rmmod hello_1

Notice that the dash was replaced by an underscore. To see what just happened in the logs:

    sudo journalctl --since "1 hour ago" | grep kernel

You now know the basics of creating, compiling, installing and removing modules. Now for more of a description of how this module works.

Kernel modules must have at least two functions: a "start" (initialization) function called `init_module()` which is called when the module is `insmod`ed into the kernel, and an "end" (cleanup) function called `cleanup_module()` which is called just before it is removed from the kernel. Actually, things have changed starting with kernel 2.3.13. You can now use whatever name you like for the start and end functions of a module, and you will learn how to do this in Section [4.2](https://wikidocs.net/196795#hello_n_goodbye). In fact, the new method is the preferred method. However, many people still use `init_module()` and `cleanup_module()` for their start and end functions.

Typically, `init_module()` either registers a handler for something with the kernel, or it replaces one of the kernel functions with its own code (usually code to do something and then call the original function). The `cleanup_module()` function is supposed to undo whatever `init_module()` did, so the module can be unloaded safely.

Lastly, every kernel module needs to include `<linux/module.h>`. We needed to include `<linux/printk.h>` only for the macro expansion for the `pr_alert()` log level, which you'll learn about in Section [4.1](https://wikidocs.net/196795#sec:printk).

1.  A point about coding style. Another thing which may not be immediately obvious to anyone getting started with kernel programming is that indentation within your code should be using **tabs** and **not spaces**. It is one of the coding conventions of the kernel. You may not like it, but you'll need to get used to it if you ever submit a patch upstream.

2.  Introducing print macros. <a name="sec:printk"></a> In the beginning there was `printk`, usually followed by a priority such as `KERN_INFO` or `KERN_DEBUG`. More recently this can also be expressed in abbreviated form using a set of print macros, such as `pr_info` and `pr_debug`. This just saves some mindless keyboard bashing and looks a bit neater. They can be found within [include/linux/printk.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/printk.h). Take time to read through the available priority macros.

3.  About Compiling. Kernel modules need to be compiled a bit differently from regular userspace apps. Former kernel versions required us to care much about these settings, which are usually stored in Makefiles. Although hierarchically organized, many redundant settings accumulated in sublevel Makefiles and made them large and rather difficult to maintain. Fortunately, there is a new way of doing these things, called kbuild, and the build process for external loadable modules is now fully integrated into the standard kernel build mechanism. To learn more on how to compile modules which are not part of the official kernel (such as all the examples you will find in this guide), see file [Documentation/kbuild/modules.rst](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/kbuild/modules.rst).

    Additional details about Makefiles for kernel modules are available in [Documentation/kbuild/makefiles.rst](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/kbuild/makefiles.rst). Be sure to read this and the related files before starting to hack Makefiles. It will probably save you lots of work.

    > Here is another exercise for the reader. See that comment above the return statement in `init_module()`? Change the return value to something negative, recompile and load the module again. What happens?

<a name="hello_n_goodbye"></a>

## 4.2. Hello and Goodbye

In early kernel versions you had to use the `init_module` and `cleanup_module` functions, as in the first hello world example, but these days you can name those anything you want by using the `module_init` and `module_exit` macros. These macros are defined in [include/linux/module.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/module.h). The only requirement is that your init and cleanup functions must be defined before calling the those macros, otherwise you'll get compilation errors. Here is an example of this technique:

    /*
     * hello-2.c - Demonstrating the module_init() and module_exit() macros.
     * This is preferred over using init_module() and cleanup_module().
     */
    #include <linux/init.h> /* Needed for the macros */
    #include <linux/module.h> /* Needed by all modules */
    #include <linux/printk.h> /* Needed for pr_info() */

    static int __init hello_2_init(void)
    {
        pr_info("Hello, world 2\n");
        return 0;
    }

    static void __exit hello_2_exit(void)
    {
        pr_info("Goodbye, world 2\n");
    }

    module_init(hello_2_init);
    module_exit(hello_2_exit);

    MODULE_LICENSE("GPL");

So now we have two real kernel modules under our belt. Adding another module is as simple as this:

    obj-m += hello-1.o
    obj-m += hello-2.o

    PWD := $(CURDIR)

    all:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

    clean:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean

Now have a look at [drivers/char/Makefile](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/char/Makefile) for a real world example. As you can see, some things got hardwired into the kernel (`obj-y`) but where have all those `obj-m` gone? Those familiar with shell scripts will easily be able to spot them. For those who are not, the `obj-$(CONFIG_FOO)` entries you see everywhere expand into `obj-y` or `obj-m`, depending on whether the `CONFIG_FOO` variable has been set to `y` or `m`. While we are at it, those were exactly the kind of variables that you have set in the `.config` file in the top-level directory of Linux kernel source tree, the last time when you said `make menuconfig` or something like that.

<a name="init_n_exit"></a>

## 4.3. The __init and __exit Macros

The `__init` macro causes the init function to be discarded and its memory freed once the init function finishes for built-in drivers, but not loadable modules. If you think about when the init function is invoked, this makes perfect sense.

There is also an `__initdata` which works similarly to `__init` but for init variables rather than functions.

The `__exit` macro causes the omission of the function when the module is built into the kernel, and like `__init`, has no effect for loadable modules. Again, if you consider when the cleanup function runs, this makes complete sense; built-in drivers do not need a cleanup function, while loadable modules do.

These macros are defined in [include/linux/init.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/init.h) and serve to free up kernel memory. When you boot your kernel and see something like Freeing unused kernel memory: 236k freed, this is precisely what the kernel is freeing.

    /*
     * hello-3.c - Illustrating the __init, __initdata and __exit macros.
     */
    #include <linux/init.h> /* Needed for the macros */
    #include <linux/module.h> /* Needed by all modules */
    #include <linux/printk.h> /* Needed for pr_info() */

    static int hello3_data __initdata = 3;

    static int __init hello_3_init(void)
    {
        pr_info("Hello, world %d\n", hello3_data);
        return 0;
    }

    static void __exit hello_3_exit(void)
    {
        pr_info("Goodbye, world 3\n");
    }

    module_init(hello_3_init);
    module_exit(hello_3_exit);

    MODULE_LICENSE("GPL");

<a name="modlicense"></a>

## 4.4. Licensing and Module Documentation

Honestly, who loads or even cares about proprietary modules? If you do then you might have seen something like this:

    $ sudo insmod xxxxxx.ko
    loading out-of-tree module taints kernel.
    module license 'unspecified' taints kernel.

You can use a few macros to indicate the license for your module. Some examples are "GPL", "GPL v2", "GPL and additional rights", "Dual BSD/GPL", "Dual MIT/GPL", "Dual MPL/GPL" and "Proprietary". They are defined within [include/linux/module.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/module.h).

To reference what license you're using a macro is available called `MODULE_LICENSE`. This and a few other macros describing the module are illustrated in the below example.

    /*
     * hello-4.c - Demonstrates module documentation.
     */
    #include <linux/init.h> /* Needed for the macros */
    #include <linux/module.h> /* Needed by all modules */
    #include <linux/printk.h> /* Needed for pr_info() */

    MODULE_LICENSE("GPL");
    MODULE_AUTHOR("LKMPG");
    MODULE_DESCRIPTION("A sample driver");

    static int __init init_hello_4(void)
    {
        pr_info("Hello, world 4\n");
        return 0;
    }

    static void __exit cleanup_hello_4(void)
    {
        pr_info("Goodbye, world 4\n");
    }

    module_init(init_hello_4);
    module_exit(cleanup_hello_4);

<a name="modparam"></a>

## 4.5. Passing Command Line Arguments to a Module

Modules can take command line arguments, but not with the argc/argv you might be used to.

To allow arguments to be passed to your module, declare the variables that will take the values of the command line arguments as global and then use the `module_param()` macro, (defined in [include/linux/moduleparam.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/moduleparam.h)) to set the mechanism up. At runtime, `insmod` will fill the variables with any command line arguments that are given, like `insmod mymodule.ko myvariable=5`. The variable declarations and macros should be placed at the beginning of the module for clarity. The example code should clear up my admittedly lousy explanation.

The `module_param()` macro takes 3 arguments: the name of the variable, its type and permissions for the corresponding file in sysfs. Integer types can be signed as usual or unsigned. If you'd like to use arrays of integers or strings see `module_param_array()` and `module_param_string()`.

    int myint = 3;
    module_param(myint, int, 0);

Arrays are supported too, but things are a bit different now than they were in the olden days. To keep track of the number of parameters you need to pass a pointer to a count variable as third parameter. At your option, you could also ignore the count and pass `NULL` instead. We show both possibilities here:

    int myintarray[2];
    module_param_array(myintarray, int, NULL, 0); /* not interested in count */

    short myshortarray[4];
    int count;
    module_param_array(myshortarray, short, &count, 0); /* put count into "count" variable */

A good use for this is to have the module variable's default values set, like a port or IO address. If the variables contain the default values, then perform autodetection (explained elsewhere). Otherwise, keep the current value. This will be made clear later on.

Lastly, there is a macro function, `MODULE_PARM_DESC()`, that is used to document arguments that the module can take. It takes two parameters: a variable name and a free form string describing that variable.

    /*
     * hello-5.c - Demonstrates command line argument passing to a module.
     */
    #include <linux/init.h>
    #include <linux/kernel.h> /* for ARRAY_SIZE() */
    #include <linux/module.h>
    #include <linux/moduleparam.h>
    #include <linux/printk.h>
    #include <linux/stat.h>

    MODULE_LICENSE("GPL");

    static short int myshort = 1;
    static int myint = 420;
    static long int mylong = 9999;
    static char *mystring = "blah";
    static int myintarray[2] = { 420, 420 };
    static int arr_argc = 0;

    /* module_param(foo, int, 0000)
     * The first param is the parameters name.
     * The second param is its data type.
     * The final argument is the permissions bits,
     * for exposing parameters in sysfs (if non-zero) at a later stage.
     */
    module_param(myshort, short, S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP);
    MODULE_PARM_DESC(myshort, "A short integer");
    module_param(myint, int, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
    MODULE_PARM_DESC(myint, "An integer");
    module_param(mylong, long, S_IRUSR);
    MODULE_PARM_DESC(mylong, "A long integer");
    module_param(mystring, charp, 0000);
    MODULE_PARM_DESC(mystring, "A character string");

    /* module_param_array(name, type, num, perm);
     * The first param is the parameter's (in this case the array's) name.
     * The second param is the data type of the elements of the array.
     * The third argument is a pointer to the variable that will store the number
     * of elements of the array initialized by the user at module loading time.
     * The fourth argument is the permission bits.
     */
    module_param_array(myintarray, int, &arr_argc, 0000);
    MODULE_PARM_DESC(myintarray, "An array of integers");

    static int __init hello_5_init(void)
    {
        int i;

        pr_info("Hello, world 5\n=============\n");
        pr_info("myshort is a short integer: %hd\n", myshort);
        pr_info("myint is an integer: %d\n", myint);
        pr_info("mylong is a long integer: %ld\n", mylong);
        pr_info("mystring is a string: %s\n", mystring);

        for (i = 0; i < ARRAY_SIZE(myintarray); i++)
            pr_info("myintarray[%d] = %d\n", i, myintarray[i]);

        pr_info("got %d arguments for myintarray.\n", arr_argc);
        return 0;
    }

    static void __exit hello_5_exit(void)
    {
        pr_info("Goodbye, world 5\n");
    }

    module_init(hello_5_init);
    module_exit(hello_5_exit);

I would recommend playing around with this code:

    $ sudo insmod hello-5.ko mystring="bebop" myintarray=-1
    $ sudo dmesg -t | tail -7
    myshort is a short integer: 1
    myint is an integer: 420
    mylong is a long integer: 9999
    mystring is a string: bebop
    myintarray[0] = -1
    myintarray[1] = 420
    got 1 arguments for myintarray.

    $ sudo rmmod hello-5
    $ sudo dmesg -t | tail -1
    Goodbye, world 5

    $ sudo insmod hello-5.ko mystring="supercalifragilisticexpialidocious" myintarray=-1,-1
    $ sudo dmesg -t | tail -7
    myshort is a short integer: 1
    myint is an integer: 420
    mylong is a long integer: 9999
    mystring is a string: supercalifragilisticexpialidocious
    myintarray[0] = -1
    myintarray[1] = -1
    got 2 arguments for myintarray.

    $ sudo rmmod hello-5
    $ sudo dmesg -t | tail -1
    Goodbye, world 5

    $ sudo insmod hello-5.ko mylong=hello
    insmod: ERROR: could not insert module hello-5.ko: Invalid parameters

<a name="modfiles"></a>

## 4.6. Modules Spanning Multiple Files

Sometimes it makes sense to divide a kernel module between several source files.

Here is an example of such a kernel module.

    /*
     * start.c - Illustration of multi filed modules
     */

    #include <linux/kernel.h> /* We are doing kernel work */
    #include <linux/module.h> /* Specifically, a module */

    int init_module(void)
    {
        pr_info("Hello, world - this is the kernel speaking\n");
        return 0;
    }

    MODULE_LICENSE("GPL");

The next file:

    /*
     * stop.c - Illustration of multi filed modules
     */

    #include <linux/kernel.h> /* We are doing kernel work */
    #include <linux/module.h> /* Specifically, a module  */

    void cleanup_module(void)
    {
        pr_info("Short is the life of a kernel module\n");
    }

    MODULE_LICENSE("GPL");

And finally, the makefile:

    obj-m += hello-1.o
    obj-m += hello-2.o
    obj-m += hello-3.o
    obj-m += hello-4.o
    obj-m += hello-5.o
    obj-m += startstop.o
    startstop-objs := start.o stop.o

    PWD := $(CURDIR)

    all:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

    clean:
        make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean

This is the complete makefile for all the examples we have seen so far. The first five lines are nothing special, but for the last example we will need two lines. First we invent an object name for our combined module, second we tell `make` what object files are part of that module.

<a name="precompiled"></a>

## 4.7. Building modules for a precompiled kernel

Obviously, we strongly suggest you to recompile your kernel, so that you can enable a number of useful debugging features, such as forced module unloading (`MODULE_FORCE_UNLOAD`): when this option is enabled, you can force the kernel to unload a module even when it believes it is unsafe, via a `sudo rmmod -f module` command. This option can save you a lot of time and a number of reboots during the development of a module. If you do not want to recompile your kernel then you should consider running the examples within a test distribution on a virtual machine. If you mess anything up then you can easily reboot or restore the virtual machine (VM).

There are a number of cases in which you may want to load your module into a precompiled running kernel, such as the ones shipped with common Linux distributions, or a kernel you have compiled in the past. In certain circumstances you could require to compile and insert a module into a running kernel which you are not allowed to recompile, or on a machine that you prefer not to reboot. If you can't think of a case that will force you to use modules for a precompiled kernel you might want to skip this and treat the rest of this chapter as a big footnote.

Now, if you just install a kernel source tree, use it to compile your kernel module and you try to insert your module into the kernel, in most cases you would obtain an error as follows:

    insmod: ERROR: could not insert module poet.ko: Invalid module format

Less cryptic information is logged to the systemd journal:

    kernel: poet: disagrees about version of symbol module_layout

In other words, your kernel refuses to accept your module because version strings (more precisely, *version magic*, see [include/linux/vermagic.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/vermagic.h)) do not match. Incidentally, version magic strings are stored in the module object in the form of a static string, starting with `vermagic:`. Version data are inserted in your module when it is linked against the `kernel/module.o` file. To inspect version magics and other strings stored in a given module, issue the command `modinfo module.ko`:

    $ modinfo hello-4.ko
    description:    A sample driver
    author:         LKMPG
    license:        GPL
    srcversion:     B2AA7FBFCC2C39AED665382
    depends:
    retpoline:      Y
    name:           hello_4
    vermagic:       5.4.0-70-generic SMP mod_unload modversions

To overcome this problem we could resort to the `--force-vermagic` option, but this solution is potentially unsafe, and unquestionably unacceptable in production modules. Consequently, we want to compile our module in an environment which was identical to the one in which our precompiled kernel was built. How to do this, is the subject of the remainder of this chapter.

First of all, make sure that a kernel source tree is available, having exactly the same version as your current kernel. Then, find the configuration file which was used to compile your precompiled kernel. Usually, this is available in your current `boot` directory, under a name like `config-5.14.x`. You may just want to copy it to your kernel source tree: `` cp /boot/config-`uname -r` .config ``.

Let's focus again on the previous error message: a closer look at the version magic strings suggests that, even with two configuration files which are exactly the same, a slight difference in the version magic could be possible, and it is sufficient to prevent insertion of the module into the kernel. That slight difference, namely the custom string which appears in the module's version magic and not in the kernel's one, is due to a modification with respect to the original, in the makefile that some distributions include. Then, examine your `Makefile`, and make sure that the specified version information matches exactly the one used for your current kernel. For example, your makefile could start as follows:

    VERSION = 5
    PATCHLEVEL = 14
    SUBLEVEL = 0
    EXTRAVERSION = -rc2

In this case, you need to restore the value of symbol **EXTRAVERSION** to **-rc2**. We suggest to keep a backup copy of the makefile used to compile your kernel available in `/lib/modules/5.14.0-rc2/build`. A simple command as following should suffice.

    cp /lib/modules/`uname -r`/build/Makefile linux-`uname -r`

Here `` linux-`uname -r` `` is the Linux kernel source you are attempting to build.

Now, please run `make` to update configuration and version headers and objects:

    $ make
      SYNC    include/config/auto.conf.cmd
      HOSTCC  scripts/basic/fixdep
      HOSTCC  scripts/kconfig/conf.o
      HOSTCC  scripts/kconfig/confdata.o
      HOSTCC  scripts/kconfig/expr.o
      LEX     scripts/kconfig/lexer.lex.c
      YACC    scripts/kconfig/parser.tab.[ch]
      HOSTCC  scripts/kconfig/preprocess.o
      HOSTCC  scripts/kconfig/symbol.o
      HOSTCC  scripts/kconfig/util.o
      HOSTCC  scripts/kconfig/lexer.lex.o
      HOSTCC  scripts/kconfig/parser.tab.o
      HOSTLD  scripts/kconfig/conf

If you do not desire to actually compile the kernel, you can interrupt the build process (CTRL-C) just after the SPLIT line, because at that time, the files you need are ready. Now you can turn back to the directory of your module and compile it: It will be built exactly according to your current kernel settings, and it will load into it without any errors.
