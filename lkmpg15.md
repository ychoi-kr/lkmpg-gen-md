15. 15.1. Interrupt Handlers

<a name="sec:irq"></a>
## 15.1. Interrupt Handlers

Except for the last chapter, everything we did in the kernel so far we have done as a response to a process asking for it, either by dealing with a special file, sending an `ioctl()`, or issuing a system call. But the job of the kernel is not just to respond to process requests. Another job, which is every bit as important, is to speak to the hardware connected to the machine.

There are two types of interaction between the CPU and the rest of the computer's hardware. The first type is when the CPU gives orders to the hardware, the other is when the hardware needs to tell the CPU something. The second, called interrupts, is much harder to implement because it has to be dealt with when convenient for the hardware, not the CPU. Hardware devices typically have a very small amount of RAM, and if you do not read their information when available, it is lost.

Under Linux, hardware interrupts are called IRQ's (Interrupt ReQuests). There are two types of IRQ's, short and long. A short IRQ is one which is expected to take a very short period of time, during which the rest of the machine will be blocked and no other interrupts will be handled. A long IRQ is one which can take longer, and during which other interrupts may occur (but not interrupts from the same device). If at all possible, it is better to declare an interrupt handler to be long.

When the CPU receives an interrupt, it stops whatever it is doing (unless it is processing a more important interrupt, in which case it will deal with this one only when the more important one is done), saves certain parameters on the stack and calls the interrupt handler. This means that certain things are not allowed in the interrupt handler itself, because the system is in an unknown state. Linux kernel solves the problem by splitting interrupt handling into two parts. The first part executes right away and masks the interrupt line. Hardware interrupts must be handled quickly, and that is why we need the second part to handle the heavy work deferred from an interrupt handler. Historically, BH (Linux naming for *Bottom Halves*) statistically book-keeps the deferred functions. **Softirq** and its higher level abstraction, **Tasklet**, replace BH since Linux 2.3.

The way to implement this is to call `request_irq()` to get your interrupt handler called when the relevant IRQ is received.

In practice IRQ handling can be a bit more complex. Hardware is often designed in a way that chains two interrupt controllers, so that all the IRQs from interrupt controller B are cascaded to a certain IRQ from interrupt controller A. Of course, that requires that the kernel finds out which IRQ it really was afterwards and that adds overhead. Other architectures offer some special, very low overhead, so called "fast IRQ" or FIQs. To take advantage of them requires handlers to be written in assembly language, so they do not really fit into the kernel. They can be made to work similar to the others, but after that procedure, they are no longer any faster than "common" IRQs. SMP enabled kernels running on systems with more than one processor need to solve another truckload of problems. It is not enough to know if a certain IRQs has happened, it's also important to know what CPU(s) it was for. People still interested in more details, might want to refer to "APIC" now.

This function receives the IRQ number, the name of the function, flags, a name for `/proc/interrupts` and a parameter to be passed to the interrupt handler. Usually there is a certain number of IRQs available. How many IRQs there are is hardware-dependent. The flags can include `SA_SHIRQ` to indicate you are willing to share the IRQ with other interrupt handlers (usually because a number of hardware devices sit on the same IRQ) and `SA_INTERRUPT` to indicate this is a fast interrupt. This function will only succeed if there is not already a handler on this IRQ, or if you are both willing to share.

<a name="sec:detect_button"></a>
## 15.2. Detecting button presses

Many popular single board computers, such as Raspberry Pi or Beagleboards, have a bunch of GPIO pins. Attaching buttons to those and then having a button press do something is a classic case in which you might need to use interrupts, so that instead of having the CPU waste time and battery power polling for a change in input state, it is better for the input to trigger the CPU to then run a particular handling function.

Here is an example where buttons are connected to GPIO numbers 17 and 18 and an LED is connected to GPIO 4. You can change those numbers to whatever is appropriate for your board.

    /*
     * intrpt.c - Handling GPIO with interrupts
     *
     * Based upon the RPi example by Stefan Wendler (devnull@kaltpost.de)
     * from:
     *   https://github.com/wendlers/rpi-kmod-samples
     *
     * Press one button to turn on a LED and another to turn it off.
     */

    #include <linux/gpio.h>
    #include <linux/interrupt.h>
    #include <linux/kernel.h> /* for ARRAY_SIZE() */
    #include <linux/module.h>
    #include <linux/printk.h>

    static int button_irqs[] = { -1, -1 };

    /* Define GPIOs for LEDs.
     * TODO: Change the numbers for the GPIO on your board.
     */
    static struct gpio leds[] = { { 4, GPIOF_OUT_INIT_LOW, "LED 1" } };

    /* Define GPIOs for BUTTONS
     * TODO: Change the numbers for the GPIO on your board.
     */
    static struct gpio buttons[] = { { 17, GPIOF_IN, "LED 1 ON BUTTON" },
                                     { 18, GPIOF_IN, "LED 1 OFF BUTTON" } };

    /* interrupt function triggered when a button is pressed. */
    static irqreturn_t button_isr(int irq, void *data)
    {
        /* first button */
        if (irq == button_irqs[0] && !gpio_get_value(leds[0].gpio))
            gpio_set_value(leds[0].gpio, 1);
        /* second button */
        else if (irq == button_irqs[1] && gpio_get_value(leds[0].gpio))
            gpio_set_value(leds[0].gpio, 0);

        return IRQ_HANDLED;
    }

    static int __init intrpt_init(void)
    {
        int ret = 0;

        pr_info("%s\n", __func__);

        /* register LED gpios */
        ret = gpio_request_array(leds, ARRAY_SIZE(leds));

        if (ret) {
            pr_err("Unable to request GPIOs for LEDs: %d\n", ret);
            return ret;
        }

        /* register BUTTON gpios */
        ret = gpio_request_array(buttons, ARRAY_SIZE(buttons));

        if (ret) {
            pr_err("Unable to request GPIOs for BUTTONs: %d\n", ret);
            goto fail1;
        }

        pr_info("Current button1 value: %d\n", gpio_get_value(buttons[0].gpio));

        ret = gpio_to_irq(buttons[0].gpio);

        if (ret < 0) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        button_irqs[0] = ret;

        pr_info("Successfully requested BUTTON1 IRQ # %d\n", button_irqs[0]);

        ret = request_irq(button_irqs[0], button_isr,
                          IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING,
                          "gpiomod#button1", NULL);

        if (ret) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        ret = gpio_to_irq(buttons[1].gpio);

        if (ret < 0) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        button_irqs[1] = ret;

        pr_info("Successfully requested BUTTON2 IRQ # %d\n", button_irqs[1]);

        ret = request_irq(button_irqs[1], button_isr,
                          IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING,
                          "gpiomod#button2", NULL);

        if (ret) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail3;
        }

        return 0;

    /* cleanup what has been setup so far */
    fail3:
        free_irq(button_irqs[0], NULL);

    fail2:
        gpio_free_array(buttons, ARRAY_SIZE(leds));

    fail1:
        gpio_free_array(leds, ARRAY_SIZE(leds));

        return ret;
    }

    static void __exit intrpt_exit(void)
    {
        int i;

        pr_info("%s\n", __func__);

        /* free irqs */
        free_irq(button_irqs[0], NULL);
        free_irq(button_irqs[1], NULL);

        /* turn all LEDs off */
        for (i = 0; i < ARRAY_SIZE(leds); i++)
            gpio_set_value(leds[i].gpio, 0);

        /* unregister */
        gpio_free_array(leds, ARRAY_SIZE(leds));
        gpio_free_array(buttons, ARRAY_SIZE(buttons));
    }

    module_init(intrpt_init);
    module_exit(intrpt_exit);

    MODULE_LICENSE("GPL");
    MODULE_DESCRIPTION("Handle some GPIO interrupts");

<a name="sec:bottom_half"></a>
## 15.3. Bottom Half

Suppose you want to do a bunch of stuff inside of an interrupt routine. A common way to do that without rendering the interrupt unavailable for a significant duration is to combine it with a tasklet. This pushes the bulk of the work off into the scheduler.

The example below modifies the previous example to also run an additional task when an interrupt is triggered.

    /*
     * bottomhalf.c - Top and bottom half interrupt handling
     *
     * Based upon the RPi example by Stefan Wendler (devnull@kaltpost.de)
     * from:
     *    https://github.com/wendlers/rpi-kmod-samples
     *
     * Press one button to turn on an LED and another to turn it off
     */

    #include <linux/delay.h>
    #include <linux/gpio.h>
    #include <linux/interrupt.h>
    #include <linux/module.h>
    #include <linux/printk.h>

    /* Macro DECLARE_TASKLET_OLD exists for compatibiity.
     * See https://lwn.net/Articles/830964/
     */
    #ifndef DECLARE_TASKLET_OLD
    #define DECLARE_TASKLET_OLD(arg1, arg2) DECLARE_TASKLET(arg1, arg2, 0L)
    #endif

    static int button_irqs[] = { -1, -1 };

    /* Define GPIOs for LEDs.
     * TODO: Change the numbers for the GPIO on your board.
     */
    static struct gpio leds[] = { { 4, GPIOF_OUT_INIT_LOW, "LED 1" } };

    /* Define GPIOs for BUTTONS
     * TODO: Change the numbers for the GPIO on your board.
     */
    static struct gpio buttons[] = {
        { 17, GPIOF_IN, "LED 1 ON BUTTON" },
        { 18, GPIOF_IN, "LED 1 OFF BUTTON" },
    };

    /* Tasklet containing some non-trivial amount of processing */
    static void bottomhalf_tasklet_fn(unsigned long data)
    {
        pr_info("Bottom half tasklet starts\n");
        /* do something which takes a while */
        mdelay(500);
        pr_info("Bottom half tasklet ends\n");
    }

    static DECLARE_TASKLET_OLD(buttontask, bottomhalf_tasklet_fn);

    /* interrupt function triggered when a button is pressed */
    static irqreturn_t button_isr(int irq, void *data)
    {
        /* Do something quickly right now */
        if (irq == button_irqs[0] && !gpio_get_value(leds[0].gpio))
            gpio_set_value(leds[0].gpio, 1);
        else if (irq == button_irqs[1] && gpio_get_value(leds[0].gpio))
            gpio_set_value(leds[0].gpio, 0);

        /* Do the rest at leisure via the scheduler */
        tasklet_schedule(&buttontask);

        return IRQ_HANDLED;
    }

    static int __init bottomhalf_init(void)
    {
        int ret = 0;

        pr_info("%s\n", __func__);

        /* register LED gpios */
        ret = gpio_request_array(leds, ARRAY_SIZE(leds));

        if (ret) {
            pr_err("Unable to request GPIOs for LEDs: %d\n", ret);
            return ret;
        }

        /* register BUTTON gpios */
        ret = gpio_request_array(buttons, ARRAY_SIZE(buttons));

        if (ret) {
            pr_err("Unable to request GPIOs for BUTTONs: %d\n", ret);
            goto fail1;
        }

        pr_info("Current button1 value: %d\n", gpio_get_value(buttons[0].gpio));

        ret = gpio_to_irq(buttons[0].gpio);

        if (ret < 0) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        button_irqs[0] = ret;

        pr_info("Successfully requested BUTTON1 IRQ # %d\n", button_irqs[0]);

        ret = request_irq(button_irqs[0], button_isr,
                          IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING,
                          "gpiomod#button1", NULL);

        if (ret) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        ret = gpio_to_irq(buttons[1].gpio);

        if (ret < 0) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail2;
        }

        button_irqs[1] = ret;

        pr_info("Successfully requested BUTTON2 IRQ # %d\n", button_irqs[1]);

        ret = request_irq(button_irqs[1], button_isr,
                          IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING,
                          "gpiomod#button2", NULL);

        if (ret) {
            pr_err("Unable to request IRQ: %d\n", ret);
            goto fail3;
        }

        return 0;

    /* cleanup what has been setup so far */
    fail3:
        free_irq(button_irqs[0], NULL);

    fail2:
        gpio_free_array(buttons, ARRAY_SIZE(leds));

    fail1:
        gpio_free_array(leds, ARRAY_SIZE(leds));

        return ret;
    }

    static void __exit bottomhalf_exit(void)
    {
        int i;

        pr_info("%s\n", __func__);

        /* free irqs */
        free_irq(button_irqs[0], NULL);
        free_irq(button_irqs[1], NULL);

        /* turn all LEDs off */
        for (i = 0; i < ARRAY_SIZE(leds); i++)
            gpio_set_value(leds[i].gpio, 0);

        /* unregister */
        gpio_free_array(leds, ARRAY_SIZE(leds));
        gpio_free_array(buttons, ARRAY_SIZE(buttons));
    }

    module_init(bottomhalf_init);
    module_exit(bottomhalf_exit);

    MODULE_LICENSE("GPL");
    MODULE_DESCRIPTION("Interrupt with top and bottom half");
