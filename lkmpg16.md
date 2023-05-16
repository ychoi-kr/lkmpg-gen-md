16. Crypto

At the dawn of the internet, everybody trusted everybody completely...but that did not work out so well. When this guide was originally written, it was a more innocent era in which almost nobody actually gave a damn about crypto - least of all kernel developers. That is certainly no longer the case now. To handle crypto stuff, the kernel has its own API enabling common methods of encryption, decryption and your favourite hash functions.

<a name="sec:hashfunc"></a>
## 16.1. Hash functions

Calculating and checking the hashes of things is a common operation. Here is a demonstration of how to calculate a sha256 hash within a kernel module. To provide the sha256 algorithm support, make sure `CONFIG_CRYPTO_SHA256` is enabled in kernel.

    /*
     * cryptosha256.c
     */
    #include <crypto/internal/hash.h>
    #include <linux/module.h>

    #define SHA256_LENGTH 32

    static void show_hash_result(char *plaintext, char *hash_sha256)
    {
        int i;
        char str[SHA256_LENGTH * 2 + 1];

        pr_info("sha256 test for string: "%s"\n", plaintext);
        for (i = 0; i < SHA256_LENGTH; i++)
            sprintf(&str[i * 2], "%02x", (unsigned char)hash_sha256[i]);
        str[i * 2] = 0;
        pr_info("%s\n", str);
    }

    static int cryptosha256_init(void)
    {
        char *plaintext = "This is a test";
        char hash_sha256[SHA256_LENGTH];
        struct crypto_shash *sha256;
        struct shash_desc *shash;

        sha256 = crypto_alloc_shash("sha256", 0, 0);
        if (IS_ERR(sha256)) {
            pr_err(
                "%s(): Failed to allocate sha256 algorithm, enable CONFIG_CRYPTO_SHA256 and try again.\n",
                __func__);
            return -1;
        }

        shash = kmalloc(sizeof(struct shash_desc) + crypto_shash_descsize(sha256),
                        GFP_KERNEL);
        if (!shash)
            return -ENOMEM;

        shash->tfm = sha256;

        if (crypto_shash_init(shash))
            return -1;

        if (crypto_shash_update(shash, plaintext, strlen(plaintext)))
            return -1;

        if (crypto_shash_final(shash, hash_sha256))
            return -1;

        kfree(shash);
        crypto_free_shash(sha256);

        show_hash_result(plaintext, hash_sha256);

        return 0;
    }

    static void cryptosha256_exit(void)
    {
    }

    module_init(cryptosha256_init);
    module_exit(cryptosha256_exit);

    MODULE_DESCRIPTION("sha256 hash test");
    MODULE_LICENSE("GPL");

Install the module:

    sudo insmod cryptosha256.ko
    sudo dmesg

And you should see that the hash was calculated for the test string.

Finally, remove the test module:

    sudo rmmod cryptosha256

<a name="sec:org2fab20b"></a>
## 16.2. Symmetric key encryption

Here is an example of symmetrically encrypting a string using the AES algorithm and a password.

    /*
     * cryptosk.c
     */
    #include <crypto/internal/skcipher.h>
    #include <linux/crypto.h>
    #include <linux/module.h>
    #include <linux/random.h>
    #include <linux/scatterlist.h>

    #define SYMMETRIC_KEY_LENGTH 32
    #define CIPHER_BLOCK_SIZE 16

    struct tcrypt_result {
        struct completion completion;
        int err;
    };

    struct skcipher_def {
        struct scatterlist sg;
        struct crypto_skcipher *tfm;
        struct skcipher_request *req;
        struct tcrypt_result result;
        char *scratchpad;
        char *ciphertext;
        char *ivdata;
    };

    static struct skcipher_def sk;

    static void test_skcipher_finish(struct skcipher_def *sk)
    {
        if (sk->tfm)
            crypto_free_skcipher(sk->tfm);
        if (sk->req)
            skcipher_request_free(sk->req);
        if (sk->ivdata)
            kfree(sk->ivdata);
        if (sk->scratchpad)
            kfree(sk->scratchpad);
        if (sk->ciphertext)
            kfree(sk->ciphertext);
    }

    static int test_skcipher_result(struct skcipher_def *sk, int rc)
    {
        switch (rc) {
        case 0:
            break;
        case -EINPROGRESS || -EBUSY:
            rc = wait_for_completion_interruptible(&sk->result.completion);
            if (!rc && !sk->result.err) {
                reinit_completion(&sk->result.completion);
                break;
            }
            pr_info("skcipher encrypt returned with %d result %d\n", rc,
                    sk->result.err);
            break;
        default:
            pr_info("skcipher encrypt returned with %d result %d\n", rc,
                    sk->result.err);
            break;
        }

        init_completion(&sk->result.completion);

        return rc;
    }

    static void test_skcipher_callback(struct crypto_async_request *req, int error)
    {
        struct tcrypt_result *result = req->data;

        if (error == -EINPROGRESS)
            return;

        result->err = error;
        complete(&result->completion);
        pr_info("Encryption finished successfully\n");

        /* decrypt data */
    #if 0
        memset((void*)sk.scratchpad, '-', CIPHER_BLOCK_SIZE);
        ret = crypto_skcipher_decrypt(sk.req);
        ret = test_skcipher_result(&sk, ret);
        if (ret)
            return;

        sg_copy_from_buffer(&sk.sg, 1, sk.scratchpad, CIPHER_BLOCK_SIZE);
        sk.scratchpad[CIPHER_BLOCK_SIZE-1] = 0;

        pr_info("Decryption request successful\n");
        pr_info("Decrypted: %s\n", sk.scratchpad);
    #endif
    }

    static int test_skcipher_encrypt(char *plaintext, char *password,
                                     struct skcipher_def *sk)
    {
        int ret = -EFAULT;
        unsigned char key[SYMMETRIC_KEY_LENGTH];

        if (!sk->tfm) {
            sk->tfm = crypto_alloc_skcipher("cbc-aes-aesni", 0, 0);
            if (IS_ERR(sk->tfm)) {
                pr_info("could not allocate skcipher handle\n");
                return PTR_ERR(sk->tfm);
            }
        }

        if (!sk->req) {
            sk->req = skcipher_request_alloc(sk->tfm, GFP_KERNEL);
            if (!sk->req) {
                pr_info("could not allocate skcipher request\n");
                ret = -ENOMEM;
                goto out;
            }
        }

        skcipher_request_set_callback(sk->req, CRYPTO_TFM_REQ_MAY_BACKLOG,
                                      test_skcipher_callback, &sk->result);

        /* clear the key */
        memset((void *)key, '\0', SYMMETRIC_KEY_LENGTH);

        /* Use the world's favourite password */
        sprintf((char *)key, "%s", password);

        /* AES 256 with given symmetric key */
        if (crypto_skcipher_setkey(sk->tfm, key, SYMMETRIC_KEY_LENGTH)) {
            pr_info("key could not be set\n");
            ret = -EAGAIN;
            goto out;
        }
        pr_info("Symmetric key: %s\n", key);
        pr_info("Plaintext: %s\n", plaintext);

        if (!sk->ivdata) {
            /* see https://en.wikipedia.org/wiki/Initialization_vector */
            sk->ivdata = kmalloc(CIPHER_BLOCK_SIZE, GFP_KERNEL);
            if (!sk->ivdata) {
                pr_info("could not allocate ivdata\n");
                goto out;
            }
            get_random_bytes(sk->ivdata, CIPHER_BLOCK_SIZE);
        }

        if (!sk->scratchpad) {
            /* The text to be encrypted */
            sk->scratchpad = kmalloc(CIPHER_BLOCK_SIZE, GFP_KERNEL);
            if (!sk->scratchpad) {
                pr_info("could not allocate scratchpad\n");
                goto out;
            }
        }
        sprintf((char *)sk->scratchpad, "%s", plaintext);

        sg_init_one(&sk->sg, sk->scratchpad, CIPHER_BLOCK_SIZE);
        skcipher_request_set_crypt(sk->req, &sk->sg, &sk->sg, CIPHER_BLOCK_SIZE,
                                   sk->ivdata);
        init_completion(&sk->result.completion);

        /* encrypt data */
        ret = crypto_skcipher_encrypt(sk->req);
        ret = test_skcipher_result(sk, ret);
        if (ret)
            goto out;

        pr_info("Encryption request successful\n");

    out:
        return ret;
    }

    static int cryptoapi_init(void)
    {
        /* The world's favorite password */
        char *password = "password123";

        sk.tfm = NULL;
        sk.req = NULL;
        sk.scratchpad = NULL;
        sk.ciphertext = NULL;
        sk.ivdata = NULL;

        test_skcipher_encrypt("Testing", password, &sk);
        return 0;
    }

    static void cryptoapi_exit(void)
    {
        test_skcipher_finish(&sk);
    }

    module_init(cryptoapi_init);
    module_exit(cryptoapi_exit);

    MODULE_DESCRIPTION("16.2. Symmetric key encryption example");
    MODULE_LICENSE("GPL");
