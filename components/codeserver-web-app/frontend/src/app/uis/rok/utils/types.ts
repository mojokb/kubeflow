import { Volume } from "src/app/utils/types";

// Extra fileds for the Rok Api data
export interface RokToken {
  name: string;
  value: string;
}

export interface RokResponse {
  token?: RokToken;
  success: string;
  log?: string;
}

export const EMPTY_TOKEN = {
  name: "",
  value: "<null>"
};

// Types and functions for receiving a CodeserverLab
export interface CodeserverLab {
  images: string[];
  image: string;
  cpu: string;
  memory: string;
  wsvolume?: Volume;
  dtvolumes?: Volume[];
  extra?: string;
}

export function emptyCodeserverLab(): CodeserverLab {
  return {
    images: [],
    image: "",
    cpu: "",
    memory: "",
    wsvolume: {
      type: "",
      name: "",
      size: "",
      path: "",
      mode: "",
      extraFields: {}
    },
    dtvolumes: [],
    extra: "{}"
  };
}
