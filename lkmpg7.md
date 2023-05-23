7. The /proc File System

In Linux, there is an additional mechanism for the kernel and kernel modules to send information to processes --- the `/proc` file system. Originally designed to allow easy access to information about processes (hence the name), it is now used by every bit of the kernel which has something interesting to report, such as `/proc/modules` which provides the list of modules and `/proc/meminfo` which gathers memory usage statistics.

The method to use the proc file system is very similar to the one used with device drivers --- a structure is created with all the information needed for the `/proc` file, including pointers to any handler functions (in our case there is only one, the one called when somebody attempts to read from the `/proc` file). Then, `init_module` registers the structure with the kernel and `cleanup_module` unregisters it.

Normal file systems are located on a disk, rather than just in memory (which is where `/proc` is), and in that case the index-node (inode for short) number is a pointer to a disk location where the file's inode is located. The inode contains information about the file, for example the file's permissions, together with a pointer to the disk location or locations where the file's data can be found.

Because we don't get called when the file is opened or closed, there's nowhere for us to put `try_module_get` and `module_put` in this module, and if the file is opened and then the module is removed, there's no way to avoid the consequences.

Here a simple example showing how to use a `/proc` file. This is the HelloWorld for the `/proc` filesystem. There are three parts: create the file `/proc/helloworld` in the function `init_module`, return a value (and a buffer) when the file `/proc/helloworld` is read in the callback function `procfile_read`, and delete the file `/proc/helloworld` in the function `cleanup_module`.

The `/proc/helloworld` is created when the module is loaded with the function `proc_create`. The return value is a `struct proc_dir_entry`, and it will be used to configure the file `/proc/helloworld` (for example, the owner of this file). A null return value means that the creation has failed.

Every time the file `/proc/helloworld` is read, the function `procfile_read` is called. Two parameters of this function are very important: the buffer (the second parameter) and the offset (the fourth one). The content of the buffer will be returned to the application which read it (for example the `cat` command). The offset is the current position in the file. If the return value of the function is not null, then this function is called again. So be careful with this function, if it never returns zero, the read function is called endlessly.

    $ cat /proc/helloworld
    HelloWorld!

    /*
     * procfs1.c
     */

    #include <linux/kernel.h>
    #include <linux/module.h>
    #include <linux/proc_fs.h>
    #include <linux/uaccess.h>
    #include <linux/version.h>

    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
    #define HAVE_PROC_OPS
    #endif

    #define procfs_name "helloworld"

    static struct proc_dir_entry *our_proc_file;

    static ssize_t procfile_read(struct file *file_pointer, char __user *buffer,
                                 size_t buffer_length, loff_t *offset)
    {
        char s[13] = "HelloWorld!\n";
        int len = sizeof(s);
        ssize_t ret = len;

        if (*offset >= len || copy_to_user(buffer, s, len)) {
            pr_info("copy_to_user failed\n");
            ret = 0;
        } else {
            pr_info("procfile read %s\n", file_pointer->f_path.dentry->d_name.name);
            *offset += len;
        }

        return ret;
    }

    #ifdef HAVE_PROC_OPS
    static const struct proc_ops proc_file_fops = {
        .proc_read = procfile_read,
    };
    #else
    static const struct file_operations proc_file_fops = {
        .read = procfile_read,
    };
    #endif

    static int __init procfs1_init(void)
    {
        our_proc_file = proc_create(procfs_name, 0644, NULL, &proc_file_fops);
        if (NULL == our_proc_file) {
            proc_remove(our_proc_file);
            pr_alert("Error:Could not initialize /proc/%s\n", procfs_name);
            return -ENOMEM;
        }

        pr_info("/proc/%s created\n", procfs_name);
        return 0;
    }

    static void __exit procfs1_exit(void)
    {
        proc_remove(our_proc_file);
        pr_info("/proc/%s removed\n", procfs_name);
    }

    module_init(procfs1_init);
    module_exit(procfs1_exit);

    MODULE_LICENSE("GPL");

<a name="sec:proc_ops"></a>

## 7.1. The proc_ops Structure

The `proc_ops` structure is defined in [include/linux/proc_fs.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/proc_fs.h) in Linux v5.6+. In older kernels, it used `file_operations` for custom hooks in `/proc` file system, but it contains some members that are unnecessary in VFS, and every time VFS expands `file_operations` set, `/proc` code comes bloated. On the other hand, not only the space, but also some operations were saved by this structure to improve its performance. For example, the file which never disappears in `/proc` can set the `proc_flag` as `PROC_ENTRY_PERMANENT` to save 2 atomic ops, 1 allocation, 1 free in per open/read/close sequence.

<a name="sec:read_write_procfs"></a>

## 7.2. Read and Write a /proc File

We have seen a very simple example for a `/proc` file where we only read the file `/proc/helloworld`. It is also possible to write in a `/proc` file. It works the same way as read, a function is called when the `/proc` file is written. But there is a little difference with read, data comes from user, so you have to import data from user space to kernel space (with `copy_from_user` or `get_user`)

The reason for `copy_from_user` or `get_user` is that Linux memory (on Intel architecture, it may be different under some other processors) is segmented. This means that a pointer, by itself, does not reference a unique location in memory, only a location in a memory segment, and you need to know which memory segment it is to be able to use it. There is one memory segment for the kernel, and one for each of the processes.

The only memory segment accessible to a process is its own, so when writing regular programs to run as processes, there is no need to worry about segments. When you write a kernel module, normally you want to access the kernel memory segment, which is handled automatically by the system. However, when the content of a memory buffer needs to be passed between the currently running process and the kernel, the kernel function receives a pointer to the memory buffer which is in the process segment. The `put_user` and `get_user` macros allow you to access that memory. These functions handle only one character, you can handle several characters with `copy_to_user` and `copy_from_user`. As the buffer (in read or write function) is in kernel space, for write function you need to import data because it comes from user space, but not for the read function because data is already in kernel space.

    /*
     * procfs2.c -  create a "file" in /proc
     */

    #include <linux/kernel.h> /* We're doing kernel work */
    #include <linux/module.h> /* Specifically, a module */
    #include <linux/proc_fs.h> /* Necessary because we use the proc fs */
    #include <linux/uaccess.h> /* for copy_from_user */
    #include <linux/version.h>

    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
    #define HAVE_PROC_OPS
    #endif

    #define PROCFS_MAX_SIZE 1024
    #define PROCFS_NAME "buffer1k"

    /* This structure hold information about the /proc file */
    static struct proc_dir_entry *our_proc_file;

    /* The buffer used to store character for this module */
    static char procfs_buffer[PROCFS_MAX_SIZE];

    /* The size of the buffer */
    static unsigned long procfs_buffer_size = 0;

    /* This function is called then the /proc file is read */
    static ssize_t procfile_read(struct file *file_pointer, char __user *buffer,
                                 size_t buffer_length, loff_t *offset)
    {
        char s[13] = "HelloWorld!\n";
        int len = sizeof(s);
        ssize_t ret = len;

        if (*offset >= len || copy_to_user(buffer, s, len)) {
            pr_info("copy_to_user failed\n");
            ret = 0;
        } else {
            pr_info("procfile read %s\n", file_pointer->f_path.dentry->d_name.name);
            *offset += len;
        }

        return ret;
    }

    /* This function is called with the /proc file is written. */
    static ssize_t procfile_write(struct file *file, const char __user *buff,
                                  size_t len, loff_t *off)
    {
        procfs_buffer_size = len;
        if (procfs_buffer_size > PROCFS_MAX_SIZE)
            procfs_buffer_size = PROCFS_MAX_SIZE;

        if (copy_from_user(procfs_buffer, buff, procfs_buffer_size))
            return -EFAULT;

        procfs_buffer[procfs_buffer_size & (PROCFS_MAX_SIZE - 1)] = '\0';
        *off += procfs_buffer_size;
        pr_info("procfile write %s\n", procfs_buffer);

        return procfs_buffer_size;
    }

    #ifdef HAVE_PROC_OPS
    static const struct proc_ops proc_file_fops = {
        .proc_read = procfile_read,
        .proc_write = procfile_write,
    };
    #else
    static const struct file_operations proc_file_fops = {
        .read = procfile_read,
        .write = procfile_write,
    };
    #endif

    static int __init procfs2_init(void)
    {
        our_proc_file = proc_create(PROCFS_NAME, 0644, NULL, &proc_file_fops);
        if (NULL == our_proc_file) {
            proc_remove(our_proc_file);
            pr_alert("Error:Could not initialize /proc/%s\n", PROCFS_NAME);
            return -ENOMEM;
        }

        pr_info("/proc/%s created\n", PROCFS_NAME);
        return 0;
    }

    static void __exit procfs2_exit(void)
    {
        proc_remove(our_proc_file);
        pr_info("/proc/%s removed\n", PROCFS_NAME);
    }

    module_init(procfs2_init);
    module_exit(procfs2_exit);

    MODULE_LICENSE("GPL");

<a name="sec:manage_procfs"></a>

## 7.3. Manage /proc file with standard filesystem

We have seen how to read and write a `/proc` file with the `/proc` interface. But it is also possible to manage `/proc` file with inodes. The main concern is to use advanced functions, like permissions.

In Linux, there is a standard mechanism for file system registration. Since every file system has to have its own functions to handle inode and file operations, there is a special structure to hold pointers to all those functions, `struct inode_operations`, which includes a pointer to `struct proc_ops`.

The difference between file and inode operations is that file operations deal with the file itself whereas inode operations deal with ways of referencing the file, such as creating links to it.

In `/proc`, whenever we register a new file, we're allowed to specify which `struct inode_operations` will be used to access to it. This is the mechanism we use, a `struct inode_operations` which includes a pointer to a `struct proc_ops` which includes pointers to our `procf_read` and `procfs_write` functions.

Another interesting point here is the `module_permission` function. This function is called whenever a process tries to do something with the `/proc` file, and it can decide whether to allow access or not. Right now it is only based on the operation and the uid of the current user (as available in current, a pointer to a structure which includes information on the currently running process), but it could be based on anything we like, such as what other processes are doing with the same file, the time of day, or the last input we received.

It is important to note that the standard roles of read and write are reversed in the kernel. Read functions are used for output, whereas write functions are used for input. The reason for that is that read and write refer to the user's point of view --- if a process reads something from the kernel, then the kernel needs to output it, and if a process writes something to the kernel, then the kernel receives it as input.

    /*
     * procfs3.c
     */

    #include <linux/kernel.h>
    #include <linux/module.h>
    #include <linux/proc_fs.h>
    #include <linux/sched.h>
    #include <linux/uaccess.h>
    #include <linux/version.h>
    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
    #include <linux/minmax.h>
    #endif

    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
    #define HAVE_PROC_OPS
    #endif

    #define PROCFS_MAX_SIZE 2048UL
    #define PROCFS_ENTRY_FILENAME "buffer2k"

    static struct proc_dir_entry *our_proc_file;
    static char procfs_buffer[PROCFS_MAX_SIZE];
    static unsigned long procfs_buffer_size = 0;

    static ssize_t procfs_read(struct file *filp, char __user *buffer,
                               size_t length, loff_t *offset)
    {
        if (*offset || procfs_buffer_size == 0) {
            pr_debug("procfs_read: END\n");
            *offset = 0;
            return 0;
        }
        procfs_buffer_size = min(procfs_buffer_size, length);
        if (copy_to_user(buffer, procfs_buffer, procfs_buffer_size))
            return -EFAULT;
        *offset += procfs_buffer_size;

        pr_debug("procfs_read: read %lu bytes\n", procfs_buffer_size);
        return procfs_buffer_size;
    }
    static ssize_t procfs_write(struct file *file, const char __user *buffer,
                                size_t len, loff_t *off)
    {
        procfs_buffer_size = min(PROCFS_MAX_SIZE, len);
        if (copy_from_user(procfs_buffer, buffer, procfs_buffer_size))
            return -EFAULT;
        *off += procfs_buffer_size;

        pr_debug("procfs_write: write %lu bytes\n", procfs_buffer_size);
        return procfs_buffer_size;
    }
    static int procfs_open(struct inode *inode, struct file *file)
    {
        try_module_get(THIS_MODULE);
        return 0;
    }
    static int procfs_close(struct inode *inode, struct file *file)
    {
        module_put(THIS_MODULE);
        return 0;
    }

    #ifdef HAVE_PROC_OPS
    static struct proc_ops file_ops_4_our_proc_file = {
        .proc_read = procfs_read,
        .proc_write = procfs_write,
        .proc_open = procfs_open,
        .proc_release = procfs_close,
    };
    #else
    static const struct file_operations file_ops_4_our_proc_file = {
        .read = procfs_read,
        .write = procfs_write,
        .open = procfs_open,
        .release = procfs_close,
    };
    #endif

    static int __init procfs3_init(void)
    {
        our_proc_file = proc_create(PROCFS_ENTRY_FILENAME, 0644, NULL,
                                    &file_ops_4_our_proc_file);
        if (our_proc_file == NULL) {
            remove_proc_entry(PROCFS_ENTRY_FILENAME, NULL);
            pr_debug("Error: Could not initialize /proc/%s\n",
                     PROCFS_ENTRY_FILENAME);
            return -ENOMEM;
        }
        proc_set_size(our_proc_file, 80);
        proc_set_user(our_proc_file, GLOBAL_ROOT_UID, GLOBAL_ROOT_GID);

        pr_debug("/proc/%s created\n", PROCFS_ENTRY_FILENAME);
        return 0;
    }

    static void __exit procfs3_exit(void)
    {
        remove_proc_entry(PROCFS_ENTRY_FILENAME, NULL);
        pr_debug("/proc/%s removed\n", PROCFS_ENTRY_FILENAME);
    }

    module_init(procfs3_init);
    module_exit(procfs3_exit);

    MODULE_LICENSE("GPL");

Still hungry for procfs examples? Well, first of all keep in mind, there are rumors around, claiming that procfs is on its way out, consider using `sysfs` instead. Consider using this mechanism, in case you want to document something kernel related yourself.

<a name="sec:manage_procfs_with_seq_file"></a>

## 7.4. Manage /proc file with seq_file

As we have seen, writing a `/proc` file may be quite "complex". So to help people writting `/proc` file, there is an API named `seq_file` that helps formating a `/proc` file for output. It is based on sequence, which is composed of 3 functions: `start()`, `next()`, and `stop()`. The `seq_file` API starts a sequence when a user read the `/proc` file.

A sequence begins with the call of the function `start()`. If the return is a non `NULL` value, the function `next()` is called. This function is an iterator, the goal is to go through all the data. Each time `next()` is called, the function `show()` is also called. It writes data values in the buffer read by the user. The function `next()` is called until it returns `NULL`. The sequence ends when `next()` returns `NULL`, then the function `stop()` is called.

BE CAREFUL: when a sequence is finished, another one starts. That means that at the end of function `stop()`, the function `start()` is called again. This loop finishes when the function `start()` returns `NULL`. You can see a scheme of this in the Figure 1.

![](https://wikidocs.net/images/page/196798/Figure1.png)

Figure 1: How seq_file works

The `seq_file` provides basic functions for `proc_ops`, such as `seq_read`, `seq_lseek`, and some others. But nothing to write in the `/proc` file. Of course, you can still use the same way as in the previous example.

    /*
     * procfs4.c -  create a "file" in /proc
     * This program uses the seq_file library to manage the /proc file.
     */

    #include <linux/kernel.h> /* We are doing kernel work */
    #include <linux/module.h> /* Specifically, a module */
    #include <linux/proc_fs.h> /* Necessary because we use proc fs */
    #include <linux/seq_file.h> /* for seq_file */
    #include <linux/version.h>

    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
    #define HAVE_PROC_OPS
    #endif

    #define PROC_NAME "iter"

    /* This function is called at the beginning of a sequence.
     * ie, when:
     *   - the /proc file is read (first time)
     *   - after the function stop (end of sequence)
     */
    static void *my_seq_start(struct seq_file *s, loff_t *pos)
    {
        static unsigned long counter = 0;

        /* beginning a new sequence? */
        if (*pos == 0) {
            /* yes => return a non null value to begin the sequence */
            return &counter;
        }

        /* no => it is the end of the sequence, return end to stop reading */
        *pos = 0;
        return NULL;
    }

    /* This function is called after the beginning of a sequence.
     * It is called untill the return is NULL (this ends the sequence).
     */
    static void *my_seq_next(struct seq_file *s, void *v, loff_t *pos)
    {
        unsigned long *tmp_v = (unsigned long *)v;
        (*tmp_v)++;
        (*pos)++;
        return NULL;
    }

    /* This function is called at the end of a sequence. */
    static void my_seq_stop(struct seq_file *s, void *v)
    {
        /* nothing to do, we use a static value in start() */
    }

    /* This function is called for each "step" of a sequence. */
    static int my_seq_show(struct seq_file *s, void *v)
    {
        loff_t *spos = (loff_t *)v;

        seq_printf(s, "%Ld\n", *spos);
        return 0;
    }

    /* This structure gather "function" to manage the sequence */
    static struct seq_operations my_seq_ops = {
        .start = my_seq_start,
        .next = my_seq_next,
        .stop = my_seq_stop,
        .show = my_seq_show,
    };

    /* This function is called when the /proc file is open. */
    static int my_open(struct inode *inode, struct file *file)
    {
        return seq_open(file, &my_seq_ops);
    };

    /* This structure gather "function" that manage the /proc file */
    #ifdef HAVE_PROC_OPS
    static const struct proc_ops my_file_ops = {
        .proc_open = my_open,
        .proc_read = seq_read,
        .proc_lseek = seq_lseek,
        .proc_release = seq_release,
    };
    #else
    static const struct file_operations my_file_ops = {
        .open = my_open,
        .read = seq_read,
        .llseek = seq_lseek,
        .release = seq_release,
    };
    #endif

    static int __init procfs4_init(void)
    {
        struct proc_dir_entry *entry;

        entry = proc_create(PROC_NAME, 0, NULL, &my_file_ops);
        if (entry == NULL) {
            remove_proc_entry(PROC_NAME, NULL);
            pr_debug("Error: Could not initialize /proc/%s\n", PROC_NAME);
            return -ENOMEM;
        }

        return 0;
    }

    static void __exit procfs4_exit(void)
    {
        remove_proc_entry(PROC_NAME, NULL);
        pr_debug("/proc/%s removed\n", PROC_NAME);
    }

    module_init(procfs4_init);
    module_exit(procfs4_exit);

    MODULE_LICENSE("GPL");

If you want more information, you can read this web page:

-   <https://lwn.net/Articles/22355/>

-   <https://kernelnewbies.org/Documents/SeqFileHowTo>

You can also read the code of [fs/seq_file.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/fs/seq_file.c) in the linux kernel.
