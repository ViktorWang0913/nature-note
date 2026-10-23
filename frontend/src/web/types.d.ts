declare module '*.vue' {import type {DefineComponent} from 'vue';const component:DefineComponent;export default component;}
declare module 'coordtransform' {const transform:{wgs84togcj02(longitude:number,latitude:number):[number,number]};export default transform;}
