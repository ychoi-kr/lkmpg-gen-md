21. Where To Go From Here?

For people seriously interested in kernel programming, I recommend [kernelnewbies.org](https://kernelnewbies.org) and the [Documentation](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation) subdirectory within the kernel source code which is not always easy to understand but can be a starting point for further investigation. Also, as Linus Torvalds said, the best way to learn the kernel is to read the source code yourself.

If you would like to contribute to this guide or notice anything glaringly wrong, please create an issue at <https://github.com/sysprog21/lkmpg>. Your pull requests will be appreciated.

Happy hacking!

[^1]: The goal of threaded interrupts is to push more of the work to separate threads, so that the minimum needed for acknowledging an interrupt is reduced, and therefore the time spent handling the interrupt (where it can't handle any other interrupts at the same time) is reduced. See <https://lwn.net/Articles/302043/>.
