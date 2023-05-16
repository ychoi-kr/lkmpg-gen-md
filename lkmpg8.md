8. sysfs: Interacting with your module

*sysfs* allows you to interact with the running kernel from userspace by reading or setting variables inside of modules. This can be useful for debugging purposes, or just as an interface for applications or scripts. You can find sysfs directories and files under the `/sys` directory on your system.

    ls -l /sys

Attributes can be exported for kobjects in the form of regular files in the filesystem. Sysfs forwards file I/O operations to methods defined for the attributes, providing a means to read and write kernel attributes.

An attribute definition in simply:

    struct attribute {
        char *name;
        struct module *owner;
        umode_t mode;
    };

    int sysfs_create_file(struct kobject * kobj, const struct attribute * attr);
    void sysfs_remove_file(struct kobject * kobj, const struct attribute * attr);

For example, the driver model defines `struct device_attribute` like:

    struct device_attribute {
        struct attribute attr;
        ssize_t (*show)(struct device *dev, struct device_attribute *attr,
                        char *buf);
        ssize_t (*store)(struct device *dev, struct device_attribute *attr,
                        const char *buf, size_t count);
    };

    int device_create_file(struct device *, const struct device_attribute *);
    void device_remove_file(struct device *, const struct device_attribute *);

To read or write attributes, `show()` or `store()` method must be specified when declaring the attribute. For the common cases [include/linux/sysfs.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/sysfs.h) provides convenience macros (`__ATTR`, `__ATTR_RO`, `__ATTR_WO`, etc.) to make defining attributes easier as well as making code more concise and readable.

An example of a hello world module which includes the creation of a variable accessible via sysfs is given below.

    /*
     * hello-sysfs.c sysfs example
     */
    #include <linux/fs.h>
    #include <linux/init.h>
    #include <linux/kobject.h>
    #include <linux/module.h>
    #include <linux/string.h>
    #include <linux/sysfs.h>

    static struct kobject *mymodule;

    /* the variable you want to be able to change */
    static int myvariable = 0;

    static ssize_t myvariable_show(struct kobject *kobj,
                                   struct kobj_attribute *attr, char *buf)
    {
        return sprintf(buf, "%d\n", myvariable);
    }

    static ssize_t myvariable_store(struct kobject *kobj,
                                    struct kobj_attribute *attr, char *buf,
                                    size_t count)
    {
        sscanf(buf, "%du", &myvariable);
        return count;
    }

    static struct kobj_attribute myvariable_attribute =
        __ATTR(myvariable, 0660, myvariable_show, (void *)myvariable_store);

    static int __init mymodule_init(void)
    {
        int error = 0;

        pr_info("mymodule: initialised\n");

        mymodule = kobject_create_and_add("mymodule", kernel_kobj);
        if (!mymodule)
            return -ENOMEM;

        error = sysfs_create_file(mymodule, &myvariable_attribute.attr);
        if (error) {
            pr_info("failed to create the myvariable file "
                    "in /sys/kernel/mymodule\n");
        }

        return error;
    }

    static void __exit mymodule_exit(void)
    {
        pr_info("mymodule: Exit success\n");
        kobject_put(mymodule);
    }

    module_init(mymodule_init);
    module_exit(mymodule_exit);

    MODULE_LICENSE("GPL");

Make and install the module:

    make
    sudo insmod hello-sysfs.ko

Check that it exists:

    sudo lsmod | grep hello_sysfs

What is the current value of `myvariable` ?

    cat /sys/kernel/mymodule/myvariable

Set the value of `myvariable` and check that it changed.

    echo "32" > /sys/kernel/mymodule/myvariable
    cat /sys/kernel/mymodule/myvariable

Finally, remove the test module:

    sudo rmmod hello_sysfs

In the above case, we use a simple kobject to create a directory under sysfs, and communicate with its attributes. Since Linux v2.6.0, the `kobject` structure made its appearance. It was initially meant as a simple way of unifying kernel code which manages reference counted objects. After a bit of mission creep, it is now the glue that holds much of the device model and its sysfs interface together. For more information about kobject and sysfs, see [Documentation/driver-api/driver-model/driver.rst](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/driver-api/driver-model/driver.rst) and <https://lwn.net/Articles/51437/>.
