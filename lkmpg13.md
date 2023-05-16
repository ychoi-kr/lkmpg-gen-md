13. Replacing Print Macros

## Replacement

In Section [1.7](196792#sec:using_x), I said that X Window System and kernel module programming do not mix. That is true for developing kernel modules. But in actual use, you want to be able to send messages to whichever tty the command to load the module came from.

"tty" is an abbreviation of *teletype*: originally a combination keyboard-printer used to communicate with a Unix system, and today an abstraction for the text stream used for a Unix program, whether it is a physical terminal, an xterm on an X display, a network connection used with ssh, etc.

The way this is done is by using current, a pointer to the currently running task, to get the current task's tty structure. Then, we look inside that tty structure to find a pointer to a string write function, which we use to write a string to the tty.

    /*
     * print_string.c - Send output to the tty we're running on, regardless if
     * it is through X11, telnet, etc.  We do this by printing the string to the
     * tty associated with the current task.
     */
    #include <linux/init.h>
    #include <linux/kernel.h>
    #include <linux/module.h>
    #include <linux/sched.h> /* For current */
    #include <linux/tty.h> /* For the tty declarations */

    static void print_string(char *str)
    {
        /* The tty for the current task */
        struct tty_struct *my_tty = get_current_tty();

        /* If my_tty is NULL, the current task has no tty you can print to (i.e.,
         * if it is a daemon). If so, there is nothing we can do.
         */
        if (my_tty) {
            const struct tty_operations *ttyops = my_tty->driver->ops;
            /* my_tty->driver is a struct which holds the tty's functions,
             * one of which (write) is used to write strings to the tty.
             * It can be used to take a string either from the user's or
             * kernel's memory segment.
             *
             * The function's 1st parameter is the tty to write to, because the
             * same function would normally be used for all tty's of a certain
             * type.
             * The 2nd parameter is a pointer to a string.
             * The 3rd parameter is the length of the string.
             *
             * As you will see below, sometimes it's necessary to use
             * preprocessor stuff to create code that works for different
             * kernel versions. The (naive) approach we've taken here does not
             * scale well. The right way to deal with this is described in
             * section 2 of
             * linux/Documentation/SubmittingPatches
             */
            (ttyops->write)(my_tty, /* The tty itself */
                            str, /* String */
                            strlen(str)); /* Length */

            /* ttys were originally hardware devices, which (usually) strictly
             * followed the ASCII standard. In ASCII, to move to a new line you
             * need two characters, a carriage return and a line feed. On Unix,
             * the ASCII line feed is used for both purposes - so we can not
             * just use \n, because it would not have a carriage return and the
             * next line will start at the column right after the line feed.
             *
             * This is why text files are different between Unix and MS Windows.
             * In CP/M and derivatives, like MS-DOS and MS Windows, the ASCII
             * standard was strictly adhered to, and therefore a newline requires
             * both a LF and a CR.
             */
            (ttyops->write)(my_tty, "\015\012", 2);
        }
    }

    static int __init print_string_init(void)
    {
        print_string("The module has been inserted.  Hello world!");
        return 0;
    }

    static void __exit print_string_exit(void)
    {
        print_string("The module has been removed.  Farewell world!");
    }

    module_init(print_string_init);
    module_exit(print_string_exit);

    MODULE_LICENSE("GPL");

<a name="sec:flash_kb_led"></a>
## 13.1. Flashing keyboard LEDs

In certain conditions, you may desire a simpler and more direct way to communicate to the external world. 13.1. Flashing keyboard LEDs can be such a solution: It is an immediate way to attract attention or to display a status condition. Keyboard LEDs are present on every hardware, they are always visible, they do not need any setup, and their use is rather simple and non-intrusive, compared to writing to a tty or a file.

From v4.14 to v4.15, the timer API made a series of changes to improve memory safety. A buffer overflow in the area of a `timer_list` structure may be able to overwrite the `function` and `data` fields, providing the attacker with a way to use return-object programming (ROP) to call arbitrary functions within the kernel. Also, the function prototype of the callback, containing a `unsigned long` argument, will prevent work from any type checking. Furthermore, the function prototype with `unsigned long` argument may be an obstacle to the forward-edge protection of *control-flow integrity*. Thus, it is better to use a unique prototype to separate from the cluster that takes an `unsigned long` argument. The timer callback should be passed a pointer to the `timer_list` structure rather than an `unsigned long` argument. Then, it wraps all the information the callback needs, including the `timer_list` structure, into a larger structure, and it can use the `container_of` macro instead of the `unsigned long` value. For more information see: [Improving the kernel timers API](https://lwn.net/Articles/735887/).

Before Linux v4.14, `setup_timer` was used to initialize the timer and the `timer_list` structure looked like:

    struct timer_list {
        unsigned long expires;
        void (*function)(unsigned long);
        unsigned long data;
        u32 flags;
        /* ... */
    };

    void setup_timer(struct timer_list *timer, void (*callback)(unsigned long),
                     unsigned long data);

Since Linux v4.14, `timer_setup` is adopted and the kernel step by step converting to `timer_setup` from `setup_timer`. One of the reasons why API was changed is it need to coexist with the old version interface. Moreover, the `timer_setup` was implemented by `setup_timer` at first.

    void timer_setup(struct timer_list *timer,
                     void (*callback)(struct timer_list *), unsigned int flags);

The `setup_timer` was then removed since v4.15. As a result, the `timer_list` structure had changed to the following.

    struct timer_list {
        unsigned long expires;
        void (*function)(struct timer_list *);
        u32 flags;
        /* ... */
    };

The following source code illustrates a minimal kernel module which, when loaded, starts blinking the keyboard LEDs until it is unloaded.

    /*
     * kbleds.c - Blink keyboard leds until the module is unloaded.
     */

    #include <linux/init.h>
    #include <linux/kd.h> /* For KDSETLED */
    #include <linux/module.h>
    #include <linux/tty.h> /* For tty_struct */
    #include <linux/vt.h> /* For MAX_NR_CONSOLES */
    #include <linux/vt_kern.h> /* for fg_console */
    #include <linux/console_struct.h> /* For vc_cons */

    MODULE_DESCRIPTION("Example module illustrating the use of Keyboard LEDs.");

    static struct timer_list my_timer;
    static struct tty_driver *my_driver;
    static unsigned long kbledstatus = 0;

    #define BLINK_DELAY HZ / 5
    #define ALL_LEDS_ON 0x07
    #define RESTORE_LEDS 0xFF

    /* Function my_timer_func blinks the keyboard LEDs periodically by invoking
     * command KDSETLED of ioctl() on the keyboard driver. To learn more on virtual
     * terminal ioctl operations, please see file:
     *   drivers/tty/vt/vt_ioctl.c, function vt_ioctl().
     *
     * The argument to KDSETLED is alternatively set to 7 (thus causing the led
     * mode to be set to LED_SHOW_IOCTL, and all the leds are lit) and to 0xFF
     * (any value above 7 switches back the led mode to LED_SHOW_FLAGS, thus
     * the LEDs reflect the actual keyboard status).  To learn more on this,
     * please see file: drivers/tty/vt/keyboard.c, function setledstate().
     */
    static void my_timer_func(struct timer_list *unused)
    {
        struct tty_struct *t = vc_cons[fg_console].d->port.tty;

        if (kbledstatus == ALL_LEDS_ON)
            kbledstatus = RESTORE_LEDS;
        else
            kbledstatus = ALL_LEDS_ON;

        (my_driver->ops->ioctl)(t, KDSETLED, kbledstatus);

        my_timer.expires = jiffies + BLINK_DELAY;
        add_timer(&my_timer);
    }

    static int __init kbleds_init(void)
    {
        int i;

        pr_info("kbleds: loading\n");
        pr_info("kbleds: fgconsole is %x\n", fg_console);
        for (i = 0; i < MAX_NR_CONSOLES; i++) {
            if (!vc_cons[i].d)
                break;
            pr_info("poet_atkm: console[%i/%i] #%i, tty %p\n", i, MAX_NR_CONSOLES,
                    vc_cons[i].d->vc_num, (void *)vc_cons[i].d->port.tty);
        }
        pr_info("kbleds: finished scanning consoles\n");

        my_driver = vc_cons[fg_console].d->port.tty->driver;
        pr_info("kbleds: tty driver magic %x\n", my_driver->magic);

        /* Set up the LED blink timer the first time. */
        timer_setup(&my_timer, my_timer_func, 0);
        my_timer.expires = jiffies + BLINK_DELAY;
        add_timer(&my_timer);

        return 0;
    }

    static void __exit kbleds_cleanup(void)
    {
        pr_info("kbleds: unloading...\n");
        del_timer(&my_timer);
        (my_driver->ops->ioctl)(vc_cons[fg_console].d->port.tty, KDSETLED,
                                RESTORE_LEDS);
    }

    module_init(kbleds_init);
    module_exit(kbleds_cleanup);

    MODULE_LICENSE("GPL");

If none of the examples in this chapter fit your debugging needs, there might yet be some other tricks to try. Ever wondered what `CONFIG_LL_DEBUG` in `make menuconfig` is good for? If you activate that you get low level access to the serial port. While this might not sound very powerful by itself, you can patch [kernel/printk.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/kernel/printk.c) or any other essential syscall to print ASCII characters, thus making it possible to trace virtually everything what your code does over a serial line. If you find yourself porting the kernel to some new and former unsupported architecture, this is usually amongst the first things that should be implemented. Logging over a netconsole might also be worth a try.

While you have seen lots of stuff that can be used to aid debugging here, there are some things to be aware of. Debugging is almost always intrusive. Adding debug code can change the situation enough to make the bug seem to disappear. Thus, you should keep debug code to a minimum and make sure it does not show up in production code.
