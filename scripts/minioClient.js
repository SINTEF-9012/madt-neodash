var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (_) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var _this = this;
var Minio = require('minio');
// Instantiate the minio client with the endpoint
// and access keys as shown below.
// var minioClient = new Minio.Client({
//   endPoint: 'play.min.io',
//   port: 9000,
//   useSSL: true,
//   accessKey: 'Q3AM3UQ867SPQQA43P2F',
//   secretKey: 'zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG',
// })
var minioEndpoint = 'localhost';
var accessKey = 'pcap-user';
var secretKey = 'pcap-user-pass';
var bucketName = 'pcap-test';
var port = 9000;
var expiryInSeconds = 60 * 60; // 1 hour
var minioClient = new Minio.Client({
    endPoint: minioEndpoint,
    accessKey: accessKey,
    secretKey: secretKey,
    useSSL: false,
    port: port
});
(function () { return __awaiter(_this, void 0, void 0, function () {
    var bucketsList;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                // console.log(`Creating Bucket: ${bucketName}`);
                // await minioClient.makeBucket(bucketName, "hello-there").catch((e) => {
                //   console.log(
                //     `Error while creating bucket '${bucketName}': ${e.message}`
                //    );
                // });
                console.log("Listing all buckets...");
                return [4 /*yield*/, minioClient.listBuckets()];
            case 1:
                bucketsList = _a.sent();
                console.log("Buckets List: ".concat(bucketsList.map(function (bucket) { return bucket.name; }).join(",\t")));
                return [2 /*return*/];
        }
    });
}); })();
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
