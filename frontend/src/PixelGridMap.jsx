import React, {
    useEffect,
    useRef,
    useState
} from "react";



const SCALE = 6;


export default function PixelGridMap() {

    const canvasRef = useRef(null);

    const [mapData, setMapData] = useState(null);



    // WebSocket 연결
    useEffect(()=>{

        const ws =
        new WebSocket(
            "ws://127.0.0.1:8000/ws/map"
        );


        ws.onopen = ()=>{
            console.log("WebSocket connected");
        };


        ws.onmessage = (event)=>{

            const data =
            JSON.parse(event.data);


            console.log(
                "MAP DATA",
                data
            );


            setMapData(data);

        };


        return ()=>{
            ws.close();
        };


    },[]);



    // 지도 그리기
    useEffect(()=>{

        if(mapData){
            drawMap();
        }

    },[mapData]);



    function drawMap(){

        const canvas =
        canvasRef.current;


        if(!canvas){
            return;
        }


        const ctx =
        canvas.getContext("2d");



        canvas.width =
        mapData.width * SCALE;


        canvas.height =
        mapData.height * SCALE;



        ctx.clearRect(
            0,
            0,
            canvas.width,
            canvas.height
        );



        for(
 let y=0;
 y<mapData.height;
 y++
){

           for(
 let x=0;
 x<mapData.width;
 x++
){


                const index =
x +
(mapData.height-y-1)
*
mapData.width;



                const value =
                mapData.data[index];



                if(value >= 65){

    // 장애물
    ctx.fillStyle = "#222222";

}
else if(value === 0){

    // 이동 가능
    ctx.fillStyle = "#ffffff";

}
else{

    // unknown
    ctx.fillStyle = "#dddddd";

}



                ctx.fillRect(

                    x*SCALE,

                    y*SCALE,

                    SCALE,

                    SCALE

                );

            }

        }



        // 그리드 표시

        ctx.strokeStyle =
        "#e5e5e5";


        ctx.lineWidth =
        0.3;



        for(
            let i=0;
            i<=mapData.height;
            i++
        ){

            ctx.beginPath();


            ctx.moveTo(
                i*SCALE,
                0
            );


            ctx.lineTo(
                i*SCALE,
                canvas.height
            );


            ctx.stroke();



            ctx.beginPath();


            ctx.moveTo(
                0,
                i*SCALE
            );


            ctx.lineTo(
                canvas.width,
                i*SCALE
            );


            ctx.stroke();

        }


    }



    return (

        <div

            style={{

                width:"100%",

                height:"100%",

                display:"flex",

                justifyContent:"center",

                alignItems:"center",

                background:"#111"

            }}

        >


            <canvas

                ref={canvasRef}


                style={{

                    imageRendering:
                    "pixelated",


                    border:
                    "2px solid #555"

                }}

            />


        </div>

    );

}