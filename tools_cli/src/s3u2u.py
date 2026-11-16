from urllib.parse import urlencode


def s3_to_console_url(s3_uri, region="us-east-2"):
    if s3_uri.startswith("s3://"):
        path = s3_uri[5:]
        bucket, *key_parts = path.split("/")
        key = "/".join(key_parts)
        query = urlencode({"region": region, "prefix": key})
        return f"https://{region}.console.aws.amazon.com/s3/buckets/{bucket}?{query}"
    else:
        return s3_uri


if __name__ == "__main__":
    import sys

    assert len(sys.argv) == 2, "Must supply 1 and only 1 argument"

    print(s3_to_console_url(sys.argv[1]))
