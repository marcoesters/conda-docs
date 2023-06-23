import os
import json



PATH_TO_INFO_JSON = '/Users/paulyim/Desktop/gh_download_test'


def load_info_json(filepath):
    with open(filepath) as f:
        json_dict = json.load(f)
        return json_dict


def main():

    # Get all filepaths to json files
    filenames = os.listdir(PATH_TO_INFO_JSON)

    # For each info.json:
    for filename in filenames:
        filepath = os.path.join(PATH_TO_INFO_JSON, filename)

        # Read info.json
        info_dict = load_info_json(filepath)

        # Parse for filename of installer
        outpath = info_dict['_outpath']

        if info_dict['_platform'] == 'win-64':
            outpath_parts = outpath.split('\\')
        else:
            outpath_parts = outpath.split('/')
        filename = outpath_parts[-1]
        print()
        print(filename)

        # Parse for openssl version
        dists = info_dict['_dists']
        for dist in dists:
            if dist.startswith('openssl'):
                print(dist)


if __name__ == '__main__':
    main()
