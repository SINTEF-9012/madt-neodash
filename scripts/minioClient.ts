var Minio = require('minio')

// Instantiate the minio client with the endpoint
// and access keys as shown below.
// var minioClient = new Minio.Client({
//   endPoint: 'play.min.io',
//   port: 9000,
//   useSSL: true,
//   accessKey: 'Q3AM3UQ867SPQQA43P2F',
//   secretKey: 'zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG',
// })

const minioEndpoint = 'localhost';
const accessKey = 'pcap-user';
const secretKey = 'pcap-user-pass';
const bucketName = 'pcap-test';
const port = 9000;
const expiryInSeconds = 60 * 60; // 1 hour

const minioClient = new Minio.Client({
  endPoint: minioEndpoint,
  accessKey: accessKey,
  secretKey: secretKey,
  useSSL: false,
  port:port,
});

(async () => {
  // console.log(`Creating Bucket: ${bucketName}`);
  // await minioClient.makeBucket(bucketName, "hello-there").catch((e) => {
  //   console.log(
  //     `Error while creating bucket '${bucketName}': ${e.message}`
  //    );
  // });

  console.log(`Listing all buckets...`);
  const bucketsList = await minioClient.listBuckets();
  console.log(
    `Buckets List: ${bucketsList.map((bucket) => bucket.name).join(",\t")}`
  );
})();

// File that needs to be uploaded.
// var file = '/tmp/photos-europe.tar'

// Make a bucket called europetrip.
// minioClient.makeBucket('europetrip', 'us-east-1', function (err) {
//   if (err) return console.log(err)

//   console.log('Bucket created successfully in "us-east-1".')

//   var metaData = {
//     'Content-Type': 'application/octet-stream',
//     'X-Amz-Meta-Testing': 1234,
//     example: 5678,
//   }
//   // Using fPutObject API upload your file to the bucket europetrip.
//   minioClient.fPutObject('europetrip', 'photos-europe.tar', file, metaData, function (err, etag) {
//     if (err) return console.log(err)
//     console.log('File uploaded successfully.')
//   })
// })

