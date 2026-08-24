import express, { Request, Response } from 'express';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.get('/health', (req: Request, res: Response) => {
    res.json({ status: 'healthy', service: 'express-service', version: '1.0.0' });
});

app.get('/', (req: Request, res: Response) => {
    res.json({ message: 'Welcome to Saleha Express Service' });
});

if (process.env.NODE_ENV !== 'test') {
    app.listen(PORT, () => {
        console.log(`Server running on port ${PORT}`);
    });
}

export default app;

